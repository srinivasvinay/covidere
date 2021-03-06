from email.mime.image import MIMEImage
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search

from django.conf import settings
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext, gettext_lazy
from django.views.generic import (CreateView, DetailView, FormView, ListView,
                                  TemplateView)

from base.models import User
from postcode.models import Postcode
from shop.forms import ShopContactForm, ShopCVRForm, ShopRegisterForm
from shop.models import Shop
from shop.tokens import account_activation_token


class ShopsListView(ListView):
    """
    Shop List View. Will list all active shops for enduser
    """
    model = Postcode
    template_name = 'shop/list.html'

    def get_queryset(self):
        queryset = self.model.objects.filter(active=True, shops__isnull=False).prefetch_related('shops')
        return queryset.order_by('postcode').distinct()


class ShopsDetailView(DetailView):
    """
    Shop Detail View. Will show detail for an active shop
    """
    model = Shop
    template_name = 'shop/detail.html'

    def get_queryset(self):
        queryset = self.model.objects.filter(active=True)
        return queryset


class ShopContactView(SuccessMessageMixin, FormView):
    """
    Contact shop form. Will send an email to the shop contact
    """
    template_name = 'shop/contact.html'
    form_class = ShopContactForm
    success_message = gettext_lazy("Message sent to shop, they will get in touch.")

    def get_success_url(self):
        return reverse('shop_detail', kwargs={'pk': self.kwargs.get('pk')})

    def form_valid(self, form):
        shop = get_object_or_404(Shop, pk=self.kwargs.get('pk'))
        send_mail(
            subject=form.cleaned_data.get('subject'),
            message=form.cleaned_data.get('message'),
            from_email=form.cleaned_data.get('email'),
            recipient_list=[shop.email],
            fail_silently=False,
        )
        return super().form_valid(form)


class ShopRegisterView(CreateView):
    """
    Contact shop form. Will send an email to the shop contact
    """
    model = Shop
    template_name = 'shop/register.html'
    form_class = ShopRegisterForm

    def get_success_url(self):
        return reverse('shop_registered')

    def form_valid(self, form):
        # Create a user, but remember to set inactive!
        user = User()
        user.username = form.cleaned_data['email']
        user.email = form.cleaned_data['email']
        user.is_active = False
        try:
            user.save()
        except IntegrityError:
            form.add_error('email', gettext('Shop with this email already exists.'))
            return super(ShopRegisterView, self).form_invalid(form)

        self.object = form.save(commit=False)
        self.object.postcode = Postcode.objects.get(postcode=form.cleaned_data['postcode_special'])
        self.object.user = user
        self.object.save()

        current_site = get_current_site(self.request)
        context = {
            'shopname': self.object.name,
            'user': user,
            'domain': current_site.domain,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': account_activation_token.make_token(user),
        }

        html_message = render_to_string('emails/account_activation.html', context)
        txt_message = render_to_string('emails/account_activation.txt', context)

        email = EmailMultiAlternatives(gettext('FOODBEE - Confirm email'), txt_message)
        email.from_email = settings.DEFAULT_FROM_EMAIL
        email.to = [self.object.email]
        email.attach_alternative(html_message, "text/html")
        email.content_subtype = 'html'
        email.mixed_subtype = 'related'

        with open('base/static/base/img/fb_logo.png', mode='rb') as f:
            image = MIMEImage(f.read())
            image.add_header('Content-ID', "<Foodbee_logo_long.png>")
            email.attach(image)

        email.send()

        return super().form_valid(form)


class ShopRegisteredView(TemplateView):
    template_name = 'shop/registered.html'


class ShopCVRLookupView(FormView):
    form_class = ShopCVRForm

    def form_valid(self, form):
        cvr = form.cleaned_data['cvr_number']

        client = Elasticsearch(
            host=settings.CVR.get('HOST'),
            port=settings.CVR.get('PORT'),
            http_auth=(settings.CVR.get('USER'), settings.CVR.get('PASS')),
        )

        query = {
            "query": {
                "bool": {
                    "must": {
                        "nested": {
                            "path": "Vrvirksomhed.virksomhedsstatus",
                            "query": {
                                "bool": {
                                    "must": [
                                        {
                                            "match": {
                                                "Vrvirksomhed.virksomhedsstatus.status": "NORMAL"
                                            }
                                        }
                                    ],
                                    "must_not": [
                                        {
                                            "exists": {
                                                "field": "Vrvirksomhed.virksomhedsstatus.periode.gyldigTil"
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    "filter": {
                        "term": {
                            "Vrvirksomhed.cvrNummer": cvr
                        }
                    }
                }
            }
        }

        s = Search(using=client, index="cvr-permanent", doc_type="virksomhed")
        s = s.source(["Vrvirksomhed.virksomhedMetadata"])
        s.update_from_dict(query)

        response = s.execute()

        if response.hits.total == 1:
            hit = response.hits[0]
            info = {}
            info['name'] = hit.Vrvirksomhed.virksomhedMetadata.nyesteNavn.navn
            address = "{0} {1}".format(
                hit.Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.vejnavn,
                hit.Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.husnummerFra
            )

            if hit.Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.bogstavFra:
                address = "{0} {1}".format(
                    address,
                    hit.Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.bogstavFra
                )

            if hit.Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.etage:
                address = "{0} {1}.".format(
                    address,
                    hit.Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.etage
                )

            if hit.Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.sidedoer:
                address = "{0} {1}".format(
                    address,
                    hit.Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.sidedoer
                )

            if hit.Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.husnummerTil:
                address = "{0} - {1}".format(
                    address,
                    hit.Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.husnummerTil
                )

            if hit.Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.bogstavTil:
                address = "{0} {1}".format(
                    address,
                    hit.Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.bogstavTil
                )

            info['address'] = address
            info['city'] = hit.Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.postdistrikt
            info['postcode'] = hit.Vrvirksomhed.virksomhedMetadata.nyesteBeliggenhedsadresse.postnummer

            # Do the api lookup and return data!
            return JsonResponse(info)
        else:
            return JsonResponse({}, status=404)

    def form_invalid(self, form):
        test = "test"
        # Something is wrong!
        return JsonResponse({}, status=400)
