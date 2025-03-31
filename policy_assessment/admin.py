from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Employee, Results, Admin

# Registering Results model
admin.site.register(Results)


# Custom User Admin with Role Field
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    fieldsets = UserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )


admin.site.register(CustomUser, CustomUserAdmin)


# Admin Model Registration
@admin.register(Admin)
class AdminAdmin(admin.ModelAdmin):
    list_display = ('A_id', 'A_name', 'A_email')


# Employee Model Registration
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('E_id', 'E_name', 'E_email', 'R_id')

