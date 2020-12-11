# Generated by Django 3.1.3 on 2020-12-10 06:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0005_auto_20201209_1127'),
    ]

    operations = [
        migrations.CreateModel(
            name='Occasion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=30)),
                ('slug', models.SlugField()),
            ],
        ),
        migrations.AddField(
            model_name='product',
            name='fabric_composition',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='fabrics',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='fit_type',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='material',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='model_height',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.CreateModel(
            name='ProductOccasion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('occasion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='shop.occasion', verbose_name='Occasion')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='shop.product', verbose_name='Product')),
            ],
            options={
                'verbose_name': 'Product Occasion',
                'verbose_name_plural': 'Product Occasions',
                'ordering': ['product', 'occasion'],
                'unique_together': {('product', 'occasion')},
            },
        ),
    ]