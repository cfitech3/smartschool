from django.contrib import admin
from .models import Etablissement, AnneeScolaire, Classe, Niveau, Division

@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    list_display = ('nom', 'type', 'code', 'is_active', 'date_creation')
    search_fields = ('nom', 'code')
    list_filter = ('type', 'is_active')

admin.site.register(AnneeScolaire)
admin.site.register(Niveau)
admin.site.register(Classe)
admin.site.register(Division)
