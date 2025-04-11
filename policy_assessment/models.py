from django.db import models

class User(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('employee', 'Employee'),
    )

    email = models.EmailField(primary_key=True)  # Primary Key
    password = models.CharField(max_length=255)
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

class Question(models.Model):
    question_text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_option = models.CharField(max_length=1, choices=[('A','A'),('B','B'),('C','C'),('D','D')])

    def __str__(self):
        return self.question_text
    
class Answer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=1)
    is_correct = models.BooleanField(default=False)
