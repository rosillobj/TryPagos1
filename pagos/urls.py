from . import views
from django.urls import path

urlpatterns = [
    path("index/",views.ClientesListView.as_view(),name="index"),
    path("detallepagos/<int:pk>/",views.PagosListView.as_view(),name="detallePagos"),
    path("paymentRegister/",views.PagoNuevoListView.as_view(),name="paymentRegister"),
    path("cortesRegister/",views.CortesView.as_view(),name="cortesRegister"),
    path("ips-disponibles/",views.IpsAvaibleView.as_view(),name='ips-disponibles' ),
    path("activarServicio/",views.ActivarServicio.as_view(),name='activarServicio' ),

    path("cortarServicio/",views.CortarServicio.as_view(),name='cortarServicio' ),
]
