# Generated by Django 2.0.3 on 2018-04-14 09:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_auto_20180331_0931'),
    ]

    operations = [
        migrations.AlterField(
            model_name='data',
            name='Link',
            field=models.CharField(max_length=500, null=True),
        ),
    ]