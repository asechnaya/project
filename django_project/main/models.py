import datetime
from django.db import models
from django.utils import timezone


# Create your models here.
class Tag(models.Model):
	name = models.CharField(max_length=50)

	def __str__(self):
		return self.name


class Document(models.Model):
	name = models.CharField(max_length=50)
	date_of_creation = models.DateField()
	content = models.TextField()
	content_type = models.CharField(max_length=30)
	tags = models.ManyToManyField(Tag, related_name="documents")
	path = models.CharField(max_length=1024)

	def __str__(self):
		return self.name


	def was_published_recently(self):
		return self.date_of_creation >= timezone.now() - datetime.timedelta(days=1)


class Question(models.Model):
	question_text = models.CharField(max_length=200)
	pub_date = models.DateTimeField('date published')

	def __str__(self):
		return self.question_text


class Choice(models.Model):
	question = models.ForeignKey(Question, on_delete=models.CASCADE)
	choice_text = models.CharField(max_length=200)
	votes = models.IntegerField(default=0)

	def __str__(self):
		return self.choice_text


