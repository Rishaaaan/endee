from django.db import models

class Dataset(models.Model):
    name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    index_name = models.CharField(max_length=100, unique=True)
    total_rows = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
