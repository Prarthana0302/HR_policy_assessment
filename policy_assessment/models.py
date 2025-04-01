from django.db import models

class User(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('employee', 'Employee'),
    )

    email = models.EmailField(primary_key=True)  # Primary Key
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='employee')

    def __str__(self):
        return f"{self.name} ({self.email}) - {self.role}"


class Result(models.Model):
    R_id = models.AutoField(primary_key=True)  # Auto-incremented primary key
    email = models.ForeignKey(User, on_delete=models.CASCADE)  # Foreign Key to User
    result_percentage = models.FloatField()  # Result%

    def __str__(self):
        return f"Result {self.R_id} - {self.email} - {self.result_percentage}%"
