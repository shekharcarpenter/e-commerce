from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.utils import IntegrityError
from django.shortcuts import render, redirect

from .models import User


# Create your views here.

def login_view(request):
    if request.method == 'POST':
        errors = []
        if not request.POST.get('email'):
            errors.append('Email is required.')
        if not request.POST.get('password'):
            errors.append('Password is required.')
        if errors:
            return render(request, 'auth/login-register.html', context={"errors": errors}, status=400)
        email = str(request.POST.get('email')).lower().strip()
        user = authenticate(username=email, password=request.POST.get('password'))
        if user is not None:
            login(request, user)
            return redirect('home:home')
        else:
            return render(request, 'auth/login-register.html', context={"errors": ["Invalid username or password."]},
                          status=401)
    else:
        return render(request, 'auth/login-register.html', status=200)


@login_required(login_url='/login')
def logout_view(request):
    logout(request)
    return redirect('home:home')


def register_view(request):
    if request.method == 'POST':
        errors = []
        required_fields = ['email', 'full_name', 'password', 'confirm_password']
        for field in required_fields:
            if not request.POST.get(field):
                errors.append(f'{field} is required.')
        if not request.POST.get('password') == request.POST.get('confirm_password'):
            errors.append('Password and Confirm password must be same.')
        if errors:
            return render(request, 'auth/login-register.html', context={"error": errors}, status=400)
        try:
            email = str(request.POST.get('email')).lower().strip()

            user = User.objects.create_user(username=email,
                                            email=email,
                                            password=request.POST.get('password'),
                                            full_name=request.POST.get('full_name'),
                                            )
            login(request, user)
        except IntegrityError as e:
            print(e)
            return render(request, 'auth/login-register.html',
                          context={"error": ['An account with this email already exists.']}, status=400)

        return redirect('home:home')

    else:
        return render(request, 'auth/login-register.html', status=200)


@login_required(login_url='/login')
def my_account(request):
    if request.method == 'GET':
        return render(request, 'accounts/account.html')
    else:
        name = request.POST.get('account_display_name')
        account_email = request.POST.get('account_email')
        password_current = request.POST.get('password_current')
        password_1 = request.POST.get('password_1')
        password_2 = request.POST.get('password_2')
        update_password = False
        errors = []
        if password_1 or password_2:
            update_password = True
            if not password_1 == password_2:
                errors.append('Password and confirm password does not match')
            if not request.user.check_password(password_current):
                errors.append('Old Password is incorrect.')
        if errors:
            context = {'errors': errors}
            return render(request, 'accounts/account.html', context=context)
        if update_password:
            request.user.set_password(password_1)
        request.user.full_name = name
        request.user.email = account_email
        request.user.save()
        return render(request, 'accounts/account.html')
