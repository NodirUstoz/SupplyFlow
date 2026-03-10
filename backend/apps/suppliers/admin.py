"""
Admin configuration for suppliers app.
"""

from django.contrib import admin

from .models import Contract, Supplier, SupplierContact, SupplierRating


class SupplierContactInline(admin.TabularInline):
    model = SupplierContact
    extra = 0


class ContractInline(admin.TabularInline):
    model = Contract
    extra = 0
    fields = ("contract_number", "title", "status", "start_date", "end_date", "total_value")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "category", "status", "country", "overall_score", "lead_time_days")
    list_filter = ("status", "category", "country", "organization")
    search_fields = ("name", "code", "email")
    inlines = [SupplierContactInline, ContractInline]
    readonly_fields = ("overall_score", "created_at", "updated_at")


@admin.register(SupplierContact)
class SupplierContactAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "supplier", "email", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("first_name", "last_name", "email")


@admin.register(SupplierRating)
class SupplierRatingAdmin(admin.ModelAdmin):
    list_display = ("supplier", "dimension", "score", "period_start", "period_end", "rated_by")
    list_filter = ("dimension",)


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("contract_number", "title", "supplier", "status", "start_date", "end_date", "total_value")
    list_filter = ("status",)
    search_fields = ("contract_number", "title")
