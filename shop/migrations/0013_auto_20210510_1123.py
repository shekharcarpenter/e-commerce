# Generated by Django 3.1.3 on 2021-05-10 05:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0012_auto_20210510_1121'),
    ]

    operations = [
        migrations.AlterField(
            model_name='test',
            name='image',
            field=models.ImageField(blank=True, default='categories/default.png', null=True, upload_to='categories', verbose_name='Image'),
        ),
    ]
