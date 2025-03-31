from django.db import models
from django.contrib.auth.models import AbstractUser
import json

class Results(models.Model):
    R_id = models.AutoField(primary_key=True)
    Result_past = models.FloatField(null=True, blank=True)
    Result_present = models.FloatField()

    def __str__(self):
        return f"Result {self.R_id} - Present: {self.Result_present}%"

class Employee(models.Model):
    E_id = models.AutoField(primary_key=True)
    E_name = models.CharField(max_length=255) 
    E_email = models.EmailField(unique=True)
    R_id = models.ForeignKey(Results, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.E_name} ({self.E_email})"
    
class Admin(models.Model):
    A_id = models.AutoField(primary_key=True)
    A_name = models.CharField(max_length=255)
    A_email = models.EmailField(unique=True)

    def __str__(self):
        return f"{self.A_name} ({self.A_email})"

    
class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('employee', 'Employee'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='employee')

    def __str__(self):
        return f"{self.username} - {self.role}"
