from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext
from django.views import View
from django.views.generic import FormView, TemplateView

from basket.forms import BasketAddForm
from product.models import Product, ProductColor, ProductSize


class Basket:
    """
    Small basket helper to add item to basket
    """
    def __init__(self, session):
        self.session = session

    def add(self, product, color, size):
        # Add or update item
        basket = self.session.setdefault('basket', [])
        item = next((item for item in basket if (
            item['product'] == product and
            item['color'] == color and
            item['size'] == size
        )), None)
        if item:
            item['count'] += 1
        else:
            basket.append(dict(
                product=product,
                color=color,
                size=size,
                count=1
            ))
        return basket


class BasketAddView(FormView):
    template_name = 'basket/add.html'
    form_class = BasketAddForm
    success_url = reverse_lazy('index')

    def form_valid(self, form):
        basket = Basket(self.request.session)
        self.request.session['basket'] = basket.add(
            form.cleaned_data.get('product'),
            form.cleaned_data.get('color'),
            form.cleaned_data.get('size'),
        )
        self.request.session.modified = True
        messages.add_message(self.request, messages.INFO, gettext('Product added to basket'))
        return super().form_valid(form)


class BasketIndexView(TemplateView):
    template_name = "basket/list.html"

    def get_context_data(self, **kwargs):
        context = super(BasketIndexView, self).get_context_data(**kwargs)
        basket = self.request.session.get('basket', [])

        # Load products
        products = {p.id: p for p in Product.objects.filter(
            pk__in=[item.get('product') for item in basket]
        ).select_related('shop')}
        # Load sizes
        sizes = {s.id: s.name for s in ProductSize.objects.filter(
            pk__in=[item.get('size') for item in basket]
        )}
        # Load colors
        colors = {c.id: c.name for c in ProductColor.objects.filter(
            pk__in=[item.get('color') for item in basket]
        )}

        new_basket = []
        total = 0

        for item in basket:
            count = item.get('count')
            price = products.get(item.get('product')).price
            subtotal = count * price
            new_item = dict(
                product_id=item.get('product'),
                product=products.get(item.get('product')).name,
                shop=products.get(item.get('product')).shop.name,
                size_id=item.get('size'),
                size=sizes.get(item.get('size')),
                color_id=item.get('color'),
                color=colors.get(item.get('color')),
                count=count,
                price=price,
                subtotal=subtotal
            )
            new_basket.append(new_item)
            total += subtotal
        context['basket'] = new_basket
        context['total'] = total

        return context


class BasketUpdateView(View):
    def post(self, request):
        action = request.POST.get('action')
        if action == 'update' or action == 'order':
            basket = request.session.get('basket', [])
            # Loop count elements and update session
            for item in request.POST:
                if item.startswith('count_'):
                    parts = item.split("_")[1:]
                    product = int(parts[0])
                    try:
                        color = int(parts[1])
                    except (TypeError, ValueError):
                        color = None
                    try:
                        size = int(parts[2])
                    except (TypeError, ValueError):
                        size = None

                    for i in range(len(basket)):
                        if basket[i]['product'] == product and basket[i]['color'] == color and basket[i]['size'] == size:
                            try:
                                count = int(request.POST.get(item))
                            except (TypeError, ValueError):
                                count = 0
                            if count > 0:
                                basket[i]['count'] = count
                            else:
                                del basket[i] 
                            break
            request.session['basket'] = basket
            request.session.modified = True

            if action == 'order':
                return redirect(reverse('order'))
            else:
                messages.add_message(self.request, messages.INFO, gettext('Basket updated'))
        elif action == 'clear':
            request.session['basket'] = []
            request.session.modified = True
            messages.add_message(self.request, messages.INFO, gettext('Basket cleared'))
        elif action.startswith('remove_'):
            parts = action.split("_")[1:]
            product = int(parts[0])
            try:
                color = int(parts[1])
            except (TypeError, ValueError):
                color = None
            try:
                size = int(parts[2])
            except (TypeError, ValueError):
                size = None
            basket = request.session.get('basket', [])
            for i in range(len(basket)):
                if basket[i]['product'] == product and basket[i]['color'] == color and basket[i]['size'] == size:
                    del basket[i]
                    messages.add_message(self.request, messages.INFO, gettext('Product removed from basket'))
                    break
            request.session['basket'] = basket
            request.session.modified = True
        return redirect(reverse('basket_index'))