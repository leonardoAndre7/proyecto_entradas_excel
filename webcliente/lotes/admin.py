from django.contrib import admin
from .models import Plano, Lote, MovimientoLote, TipoCambio


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display  = ("id", "numero", "plano", "estado", "precio", "separado_por", "separado_en", "vendido_en")
    list_filter   = ("estado", "plano", "separado_por")
    list_editable = ("numero", "estado", "precio")   # editar número/precio/estado desde la lista
    search_fields = ("id", "numero")


@admin.register(MovimientoLote)
class MovimientoLoteAdmin(admin.ModelAdmin):
    list_display = ("fecha", "lote", "estado", "usuario")
    list_filter  = ("estado", "usuario")
    date_hierarchy = "fecha"


@admin.register(TipoCambio)
class TipoCambioAdmin(admin.ModelAdmin):
    list_display = ("usd_pen", "actualizado")


admin.site.register(Plano)
