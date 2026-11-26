"""
Harnais de tests AppSec & Multi-Tenancy (Objectif 9.5/10) — SmartSchool ERP.
Couvre les 5 chantiers :
  1. Garde-fou d'isolation Multi-Tenant (`TenantSafeMixin` + fuzzing HTTP inter-écoles)
  2. Protection des médias privés (`/media/eleves/`, `/media/users/`) + purge EXIF & UUID4
  3. 2FA TOTP RFC 6238, codes de secours, invalidation de session sur changement de rôle, rate-limit SQL
  4. En-têtes CSP / Permissions-Policy / Referrer-Policy + verrouillage `/admin/`
  5. Chaînage cryptographique SHA-256 infalsifiable sur `JournalAction`
"""
import datetime
import io
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import JournalConnexion
from accounts.totp import generate_totp_code, generate_totp_secret
from core.tenancy import TenantIsolationError, set_tenant_context, reset_tenant_context
from core.validators import sanitize_uploaded_image
from eleves.models import Eleve
from etablissements.models import AnneeScolaire, Etablissement, JournalAction
from finances.models import Paiement, ReductionFrais, TypeFrais

User = get_user_model()


def _make_jpeg_bytes_with_exif() -> bytes:
    img = Image.new("RGB", (64, 64), color=(20, 100, 200))
    exif = img.getexif()
    exif[0x010E] = "Secret GPS / Metadata Test"
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


class TestAppSecEtMultiTenant95(TestCase):

    def setUp(self):
        cache.clear()
        self.etab_a = Etablissement.objects.create(nom="École Alpha", code="ALPHA95", type="lycee")
        self.etab_b = Etablissement.objects.create(nom="École Beta", code="BETA95", type="lycee")
        self.annee_a = AnneeScolaire.objects.create(
            etablissement=self.etab_a, libelle="2025-2026",
            date_debut=datetime.date(2025, 10, 1), date_fin=datetime.date(2026, 7, 31), is_active=True,
        )
        self.annee_b = AnneeScolaire.objects.create(
            etablissement=self.etab_b, libelle="2025-2026",
            date_debut=datetime.date(2025, 10, 1), date_fin=datetime.date(2026, 7, 31), is_active=True,
        )
        self.admin_a = User.objects.create_user(
            username="admin_a95", password="StrongPassword123!", role="admin", etablissement=self.etab_a,
        )
        self.admin_b = User.objects.create_user(
            username="admin_b95", password="StrongPassword123!", role="admin", etablissement=self.etab_b,
        )
        self.eleve_b = Eleve.objects.create(
            etablissement=self.etab_b, nom="Traore", prenom="Awa", sexe="F",
            date_naissance=datetime.date(2011, 4, 12),
        )
        self.tf_b = TypeFrais.objects.create(
            etablissement=self.etab_b, annee=self.annee_b, nom="Scolarité B", montant_defaut=Decimal("100000"),
        )
        self.paiement_b = Paiement.objects.create(
            etablissement=self.etab_b, eleve=self.eleve_b, annee=self.annee_b,
            type_frais=self.tf_b, montant=Decimal("50000"), encaisse_par=self.admin_b,
        )

    # ── CHANTIER 1 : Garde-fou Multi-Tenant & Fuzzing ────────────────────────
    def test_tenant_safe_mixin_bloque_ecriture_et_suppression_inter_ecoles(self):
        tokens = set_tenant_context(self.etab_a.pk, enforce=True)
        try:
            self.eleve_b.nom = "Pirate"
            with self.assertRaises(TenantIsolationError):
                self.eleve_b.save()
            with self.assertRaises(TenantIsolationError):
                self.paiement_b.delete()
        finally:
            reset_tenant_context(tokens)

    def test_fuzzing_routes_critiques_ecole_a_vers_ecole_b(self):
        self.client.force_login(self.admin_a)
        routes_get_404 = [
            reverse("detail_eleve", kwargs={"pk": self.eleve_b.pk}),
            reverse("situation_eleve", kwargs={"pk": self.eleve_b.pk}),
            reverse("recu_paiement", kwargs={"pk": self.paiement_b.pk}),
        ]
        for url in routes_get_404:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 404, f"Fuite multi-tenant sur GET {url}")

        resp_annul = self.client.post(
            reverse("annuler_paiement", kwargs={"pk": self.paiement_b.pk}),
            {"motif_annulation": "Tentative inter-tenant"},
        )
        self.assertEqual(resp_annul.status_code, 404)
        self.paiement_b.refresh_from_db()
        self.assertEqual(self.paiement_b.statut, "valide")

    # ── CHANTIER 2 : Médias privés par tenant & purge EXIF/UUID ──────────────
    def test_purge_exif_et_renommage_uuid(self):
        raw_jpeg = _make_jpeg_bytes_with_exif()
        upload = SimpleUploadedFile("eleve_secret_name.jpg", raw_jpeg, content_type="image/jpeg")
        clean_file, err = sanitize_uploaded_image(upload)
        self.assertIsNone(err)
        self.assertNotIn("eleve_secret_name", clean_file.name)
        self.assertTrue(clean_file.name.endswith(".jpg"))
        reopened = Image.open(io.BytesIO(clean_file.read()))
        self.assertEqual(len(reopened.getexif()), 0)

    def test_media_photo_eleve_privee_par_tenant(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with override_settings(MEDIA_ROOT=tmpdir):
                raw_jpeg = _make_jpeg_bytes_with_exif()
                clean_file, _ = sanitize_uploaded_image(
                    SimpleUploadedFile("photo.jpg", raw_jpeg, content_type="image/jpeg")
                )
                self.eleve_b.photo = clean_file
                self.eleve_b.save()
                media_url = f"/media/{self.eleve_b.photo.name}"

                # Anonyme -> 403
                self.client.logout()
                self.assertEqual(self.client.get(media_url).status_code, 403)

                # Admin École A -> 403
                self.client.force_login(self.admin_a)
                self.assertEqual(self.client.get(media_url).status_code, 403)

                # Admin École B -> 200 + Cache-Control private, no-store
                self.client.force_login(self.admin_b)
                resp_ok = self.client.get(media_url)
                self.assertEqual(resp_ok.status_code, 200)
                self.assertIn("no-store", resp_ok["Cache-Control"])
                resp_ok.close()

    # ── CHANTIER 3 : 2FA TOTP, Session Hash & Rate-Limit SQL ─────────────────
    def test_flux_complet_2fa_totp_et_code_secours(self):
        secret = generate_totp_secret()
        from accounts.totp import generate_backup_codes
        plain_codes, hashed_codes = generate_backup_codes(count=2)
        self.admin_a.totp_secret = secret
        self.admin_a.totp_enabled = True
        self.admin_a.totp_backup_codes = hashed_codes
        self.admin_a.save()

        # Étape 1 : mot de passe valide -> redirection vers /auth/verify-2fa/ (pas encore connecté)
        resp1 = self.client.post(reverse("login"), {
            "username": "admin_a95", "password": "StrongPassword123!",
        })
        self.assertRedirects(resp1, reverse("verify_2fa"))

        # Étape 2 : code TOTP valide -> connexion finalisée
        valid_otp = generate_totp_code(secret)
        resp2 = self.client.post(reverse("verify_2fa"), {"otp_code": valid_otp})
        self.assertEqual(resp2.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.admin_a.pk)

        # Déconnexion puis reconnexion avec code de secours à usage unique
        self.client.post(reverse("logout"))
        self.client.post(reverse("login"), {"username": "admin_a95", "password": "StrongPassword123!"})
        resp_backup = self.client.post(reverse("verify_2fa"), {"otp_code": plain_codes[0]})
        self.assertEqual(resp_backup.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.admin_a.pk)

        # Le même code de secours ne peut pas être réutilisé
        self.client.post(reverse("logout"))
        self.client.post(reverse("login"), {"username": "admin_a95", "password": "StrongPassword123!"})
        resp_reuse = self.client.post(reverse("verify_2fa"), {"otp_code": plain_codes[0]})
        self.assertEqual(resp_reuse.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    # ── Régression UI : le menu latéral (construit en JS) doit recevoir ses données ──
    def test_menu_lateral_donnees_json_et_scripts_non_imbriques(self):
        import re
        self.client.force_login(self.admin_a)
        html = self.client.get(reverse("dashboard")).content.decode("utf-8")

        # 1. Le bloc de données JSON du menu est présent
        self.assertIn('id="sidebar-menu-data"', html)

        # 2. Aucun <script> exécutable ne doit en contenir un autre (cause d'un menu vide)
        depth = 0
        for m in re.finditer(r"<script\b[^>]*>|</script>", html, re.I):
            tag = m.group(0).lower()
            if tag.startswith("</"):
                depth = max(0, depth - 1)
            else:
                self.assertEqual(depth, 0, "Balise <script> imbriquée : le JavaScript de la page est cassé")
                if "src=" not in tag:
                    depth += 1

        # 3. SMARTSCHOOL_CONTEXT est défini avant son utilisation par buildSidebar()
        self.assertLess(html.index("const SMARTSCHOOL_CONTEXT"), html.index("buildSidebar();"))

    def test_invalidation_immediate_session_si_changement_role(self):
        self.client.force_login(self.admin_a)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

        # Changement de rôle en base -> la session active doit être révoquée dès la requête suivante
        User.objects.filter(pk=self.admin_a.pk).update(role="enseignant")
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login/", resp["Location"])

    def test_rate_limit_sql_bloque_meme_si_cache_vide(self):
        for _ in range(5):
            JournalConnexion.objects.create(username="admin_a95", statut="echec", ip="127.0.0.1")
        cache.clear()  # Simule un autre worker Gunicorn sans cache mémoire partagé
        resp = self.client.post(reverse("login"), {
            "username": "admin_a95", "password": "StrongPassword123!",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    # ── CHANTIER 4 : En-têtes HTTP CSP & Verrouillage /admin/ ────────────────
    def test_security_headers_et_blocage_django_admin(self):
        self.client.force_login(self.admin_a)
        resp = self.client.get(reverse("dashboard"))
        self.assertIn("Content-Security-Policy", resp)
        self.assertIn("frame-ancestors 'none'", resp["Content-Security-Policy"])
        self.assertIn("Permissions-Policy", resp)
        self.assertEqual(resp["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertEqual(resp["Cross-Origin-Opener-Policy"], "same-origin")

        # Directeur d'établissement (non super_admin) bloqué sur /admin/
        resp_admin = self.client.get("/admin/")
        self.assertEqual(resp_admin.status_code, 403)

    # ── CHANTIER 5 : Chaînage cryptographique SHA-256 JournalAction ──────────
    def test_chaine_sha256_journal_action_detecte_alteration(self):
        j1 = JournalAction.objects.create(auteur=self.admin_a, type_action="autre", cible="A", detail="Action 1")
        j2 = JournalAction.objects.create(auteur=self.admin_b, type_action="autre", cible="B", detail="Action 2")
        self.assertEqual(j1.hash_precedent, "GENESIS")
        self.assertEqual(j2.hash_precedent, j1.hash_integrite)

        ok, count, err = JournalAction.verifier_integrite_chaine()
        self.assertTrue(ok)
        self.assertGreaterEqual(count, 2)
        self.assertIsNone(err)

        # Altération directe en SQL (contournant save()) -> détectée immédiatement
        JournalAction.objects.filter(pk=j1.pk).update(detail="Action 1 falsifiée")
        ok2, _, err2 = JournalAction.verifier_integrite_chaine()
        self.assertFalse(ok2)
        self.assertIn(f"#{j1.pk}", err2)
