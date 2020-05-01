import requests
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.utils.http import urlencode
from django.utils.text import slugify
from django.utils.translation import gettext_lazy
from phonenumber_field.modelfields import PhoneNumberField
from django.core.validators import MaxLengthValidator,MinLengthValidator
from postcode.models import Postcode

from stdimage import JPEGField

class Shop(models.Model):
    name = models.CharField(gettext_lazy("shop name"), max_length=100)
    address = models.CharField(gettext_lazy("address"), max_length=100)
    postcode = models.ForeignKey(Postcode, on_delete=models.CASCADE, related_name="shops", blank=True, null=True)
    homepage = models.URLField(gettext_lazy("homepage"))
    email = models.EmailField(gettext_lazy("contact email"))
    phone = PhoneNumberField(gettext_lazy("phone"), max_length=17, unique=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    cvr_number = models.CharField(gettext_lazy("CVR number"), unique=True, validators=[MaxLengthValidator(8),MinLengthValidator(8)], max_length=8, null=True)
    active = models.BooleanField(gettext_lazy("active"), default=False)
    
    order_pickup = models.BooleanField(gettext_lazy("offers order pickup"), default=True)
    order_delivery = models.BooleanField(gettext_lazy("offers order delivery"), default=False)
    delivery_postcode = models.ManyToManyField(Postcode, blank=True)

    shop_image = JPEGField(        
        gettext_lazy('shop_image'),
        upload_to='images/shop/%Y/%m/%d/',
        variations={'full': (600, 400, True)},
        default="images/2020/04/16/image.png",
    )

    # Internal used fields
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    location = models.PointField(blank=True, null=True)

    def __str__(self):
        return self.name

    def map_query(self):
        """
        Helper to provide the urlencoded information for a shop to google maps
        """
        data = dict(
            query=f"{self.name} {self.address} {self.postcode.postcode} {self.postcode.city}"
        )
        return urlencode(data)
    
    def slug(self):
        """
        Will convert shop.name to a slug
        """
        return slugify(f"{self.name} {self.pk}")
    
    def save(self, *args, **kwargs):
        if self.active and not self.location:
            # Fetch location from api!
            osm_url = 'https://nominatim.openstreetmap.org/search'
            query = dict(
                street=self.address,
                city=self.postcode.city,
                country="dk",
                postalcode=self.postcode.postcode,
                format="geojson"
            )
            full_url = f"{osm_url}?{urlencode(query)}"
            res = requests.get(full_url)
            coordinates = res.json().get('features')[0].get('geometry').get('coordinates')
            pnt = Point(coordinates)
            self.location = pnt
        super(Shop, self).save(*args, **kwargs)
