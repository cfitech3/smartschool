
from django import forms
from .models import Eleve, Tuteur, Inscription
from etablissements.models import Classe
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs

class EleveForm(forms.ModelForm):
    date_naissance = forms.DateField(widget=forms.DateInput(attrs={"type":"date","class":"form-control"}))
    class Meta:
        model=Eleve; fields=["nom","prenom","sexe","date_naissance","lieu_naissance","adresse","telephone","photo"]
        widgets={f:forms.TextInput(attrs={"class":"form-control"}) for f in ["nom","prenom","lieu_naissance","adresse","telephone"]}
        widgets["sexe"]=forms.Select(attrs={"class":"form-control"})
        widgets["adresse"]=forms.Textarea(attrs={"class":"form-control","rows":2})
    def __init__(self,*a,**k): self.etablissement=k.pop("etablissement",None); super().__init__(*a,**k)

class TuteurForm(forms.ModelForm):
    class Meta:
        model=Tuteur; fields=["nom","prenom","lien","telephone","telephone2","email","profession"]
        widgets={f:forms.TextInput(attrs={"class":"form-control"}) for f in ["nom","prenom","telephone","telephone2","email","profession"]}
        widgets["lien"]=forms.Select(attrs={"class":"form-control"})
    def __init__(self,*a,**k):
        self.etablissement=k.pop("etablissement",None); super().__init__(*a,**k)
        for f in self.fields.values(): f.required=False

class InscriptionForm(forms.ModelForm):
    class Meta:
        model=Inscription; fields=["classe","observations"]
        widgets={"classe":forms.Select(attrs={"class":"form-control"}),"observations":forms.Textarea(attrs={"class":"form-control","rows":2})}
    def __init__(self,*a,**k):
        self.etablissement=k.pop("etablissement",None); self.annee=k.pop("annee",None); super().__init__(*a,**k)
        if self.etablissement and self.annee:
            self.fields["classe"].queryset=get_classes_actives(self.etablissement,annee=self.annee).select_related("niveau").order_by("niveau__ordre","nom")
        self.fields["observations"].required=False
