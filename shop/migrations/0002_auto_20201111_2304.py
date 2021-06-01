# Generated by Django 3.1.3 on 2020-11-11 23:04

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('shop', '0001_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='cart',
            name='owner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='carts', to='users.user', verbose_name='Owner'),
        ),
        migrations.AlterUniqueTogether(
            name='productrecommendation',
            unique_together={('primary', 'recommendation')},
        ),
        migrations.AlterUniqueTogether(
            name='productcategory',
            unique_together={('product', 'category')},
        ),
        migrations.AlterUniqueTogether(
            name='cartproduct',
            unique_together={('cart', 'product')},
        ),
    ]
