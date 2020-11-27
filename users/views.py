from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.utils import IntegrityError
from django.shortcuts import render, redirect

from .models import User, Address


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


@login_required(login_url='/login')
def address_view(request, pk=None):
    if request.method == 'GET':
        try:
            if pk:
                address_object = Address.objects.get(id=pk)
                context = {'address': address_object}
                return render(request, 'accounts/add-address.html', context=context)
            else:
                address_object = Address.objects.filter(user=request.user)
                context = {'addresses': address_object}

        except Address.DoesNotExist:
            context = {}

        return render(request, 'accounts/address.html', context=context)
    else:

        errors = []
        required_fields = ['full_name', 'house_number', 'street', 'city', 'state']
        for field in required_fields:
            if not request.POST.get(field):
                errors.append(f'{field} is required.')
        if errors:
            return render(request, 'auth/address.html', context={"error": errors}, status=400)
        address_object = Address.objects.create(house_number=request.POST.get('house_number'),
                                                street=request.POST.get('street'),
                                                city=request.POST.get('city'),
                                                state=request.POST.get('state'),
                                                user=request.user)

        context = {'address': address_object}
        return render(request, 'auth/address.html', context=context)


@login_required(login_url='/login')
def add_address(request, address_id=None):
    # if not address_id:
    #     address_object = Address.objects.filter(user=request.user)
    #     context = {'addresses': address_object}
    #     print(context)
    #     return render(request, 'accounts/address.html', context=context)
    if request.method == 'GET':
        return render(request, 'accounts/add-address.html')
    else:
        update = request.POST.get('_method')
        errors = []
        required_fields = ['full_name', 'house_number', 'street', 'city', 'state']
        for field in required_fields:
            if not request.POST.get(field):
                errors.append(f'{field} is required.')
        if errors:
            return render(request, 'accounts/add-address.html', context={"error": errors}, status=400)
        if not update:
            Address.objects.create(house_number=request.POST.get('house_number'),
                                   street=request.POST.get('street'),
                                   city=request.POST.get('city'),
                                   state=request.POST.get('state'),
                                   user=request.user)
            return redirect('users:address')

        else:
            address_id = request.POST.get('address_id')
            full_name = request.POST.get('full_name')
            house_number = request.POST.get('house_number')
            street = request.POST.get('street')
            city = request.POST.get('city')
            pin_code = request.POST.get('pin_code')
            state = request.POST.get('state')

            address_object = Address.objects.get(id=address_id)
            address_object.house_number = house_number
            address_object.full_name = full_name
            address_object.street = street
            address_object.city = city
            address_object.state = state
            address_object.pin_code = pin_code
            address_object.save()
        return redirect('users:address')


@login_required(login_url='/login')
def delete_address(request, pk):
    deleted = Address.objects.filter(id=pk, user=request.user).delete()
    return redirect('users:address')
