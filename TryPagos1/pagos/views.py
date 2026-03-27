from django.shortcuts import render,get_object_or_404
from .models import Cliente,Pagos
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from rest_framework.generics import ListCreateAPIView,ListAPIView,DestroyAPIView,RetrieveAPIView,UpdateAPIView
from .serializers import ClienteSerializer,PagosSerializer
from rest_framework import status
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import datetime, timedelta
import ipaddress
# Create your views here.



class ClientesListView(ListAPIView):
    
    permission_classes = [IsAuthenticated]
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class PagosListView(APIView):
    permission_classes = [IsAuthenticated]
    
    
    def get(self,request,pk):
        pagos = Pagos.objects.get(id_cliente = pk)
        if(pagos):
            print("uno")
            serializer = PagosSerializer(pagos)
            return Response(status=status.HTTP_200_OK,data =serializer.data)
        else:
            return Response(status= status.HTTP_204_NO_CONTENT)
        





MONTHS = {
    1: "january", 2: "february", 3: "march", 4: "april",
    5: "may", 6: "june", 7: "july", 8: "august",
    9: "september", 10: "october", 11: "november", 12: "december"
}

class PagoNuevoListView(UpdateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Pagos.objects.all()

    def patch(self, request, *args, **kwargs):
        cliente_id = request.data.get("id")
        pago_raw   = request.data.get("pago")
        fecha_raw  = request.data.get("fecha")  # "2026-02-09"

        if not cliente_id or pago_raw is None or not fecha_raw:
            return Response(
                {"detail": "Requiere: id, pago, fecha (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # pago
        try:
            pago = int(pago_raw)
            if pago < 0:
                return Response({"detail": "El pago no puede ser negativo."},
                                status=status.HTTP_400_BAD_REQUEST)
        except (TypeError, ValueError):
            return Response({"detail": "El campo 'pago' debe ser un entero."},
                            status=status.HTTP_400_BAD_REQUEST)

        # fecha "YYYY-MM-DD"
        fecha_pago = parse_date(str(fecha_raw))
        if not fecha_pago:
            return Response({"detail": "Fecha inválida. Usa YYYY-MM-DD."},
                            status=status.HTTP_400_BAD_REQUEST)

        # buscar pagos del cliente
        try:
            pagos = Pagos.objects.get(id_cliente_id=cliente_id)
        except Pagos.DoesNotExist:
            return Response({"detail": "No existe registro de pagos para ese cliente."},
                            status=status.HTTP_404_NOT_FOUND)

        # mes seguro (no depende del idioma del servidor)
        mes_nombre = MONTHS[timezone.now().month]   # ej: "february"
        mes_p = f"{mes_nombre}_p"                   # ej: "february_p"
        mes_d = mes_nombre                          # ej: "february"

        total_anterior = getattr(pagos, mes_p) or 0
        total_nuevo = total_anterior + pago

        setattr(pagos, mes_p, total_nuevo)
        setattr(pagos, mes_d, fecha_pago)

        pagos.ultimo_pago = fecha_pago
        pagos.ultimo_pago_p = total_nuevo
        pagos.id_user = request.user

        pagos.save(update_fields=[mes_p, mes_d, "ultimo_pago", "ultimo_pago_p", "id_user"])

        return Response(
            {"mes": mes_nombre, "total_mes": total_nuevo, "fecha": str(fecha_pago)},
            status=status.HTTP_200_OK
        )

class CortesView(ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Pagos.objects.all()

    def get(self, request, *args, **kwargs):
        today = timezone.localdate()
        limite = today - timedelta(days=30)

        cortes_qs = (
            Pagos.objects
            .filter(ultimo_pago__lt=limite)
            .select_related("id_cliente", "id_user")
            .order_by("-ultimo_pago")
        )

        data = []
        for p in cortes_qs:
            c = p.id_cliente  # Cliente (o None si está null)
            data.append({
                "pago_id": p.id,
                "cliente_id": c.id if c else None,
                "cliente_nombre": getattr(c, "nombre", None),  # ajusta si tu campo se llama diferente
                "ultimo_pago": p.ultimo_pago,                 # DateField -> DRF lo serializa a "YYYY-MM-DD"
                "ultimo_pago_p": p.ultimo_pago_p,
                "id_user": p.id_user_id,                       # quién registró el último movimiento
            })

        return Response(
            {
                "limite": str(limite),
                "usuarios_count": cortes_qs.count(),
                "results": data
            },
            status=status.HTTP_200_OK
        )
class CortarServicio(UpdateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Cliente.objects.all()
    
    def patch(self, request, *args, **kwargs):
        id_ClienteRaw = request.data['cliente_id']
        print(id_ClienteRaw)
        cliente = Cliente.objects.get(id = id_ClienteRaw)
        if cliente:
            setattr(cliente,'cortado', True )
            cliente.save()
        return Response ( status=status.HTTP_200_OK)


class ActivarServicio(UpdateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Cliente.objects.all()
    
    def patch(self, request, *args, **kwargs):
        id_ClienteRaw = request.data['cliente_id']
        print(id_ClienteRaw)
        cliente = Cliente.objects.get(id = id_ClienteRaw)
        if cliente:
            setattr(cliente,'cortado', False )
            cliente.save()
        return Response ( status=status.HTTP_200_OK)


class IpsAvaibleView(ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Cliente.objects.all()

    def get(self, request, *args, **kwargs):
        start = int(request.query_params.get("start", 21))
        end = int(request.query_params.get("end", 254))
        limit = request.query_params.get("limit")
        limit = int(limit) if limit is not None else None

        if start < 0 or end > 255 or start > end:
            return Response(
                {"detail": "Rango inválido. Usa start<=end y 0..255."},
                status=status.HTTP_400_BAD_REQUEST
            )

        network = ipaddress.ip_network("192.168.1.0/24")

        # IPs reservadas / excluidas manualmente
        reserved_ips = {
            "192.168.1.99",
            "192.168.1.100",
            "192.168.1.156",
            "192.168.1.101",
            "192.168.1.127",
            "192.168.1.122",
            "192.168.1.124",
            "192.168.1.121",
            "192.168.1.129",
            "192.168.1.151",
            "192.168.1.123",
            "192.168.1.125",
            "192.168.1.110",
            "192.168.1.111",
            "192.168.1.120",
        }

        # Convertimos reservadas a último octeto
        reserved_octets = set()
        for ip_str in reserved_ips:
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                if ip_obj in network:
                    reserved_octets.add(int(str(ip_obj).split(".")[-1]))
            except ValueError:
                pass

        ocupadas_raw = (
            Cliente.objects
            .exclude(ip_completa__isnull=True)
            .exclude(ip_completa__exact="")
            .values_list("ip_completa", flat=True)
        )

        ocupadas = set()
        invalidas = []

        for ip_str in ocupadas_raw:
            ip_str = str(ip_str).strip()

            try:
                ip_obj = ipaddress.ip_address(ip_str)
            except ValueError:
                invalidas.append(ip_str)
                continue

            if ip_obj in network:
                ocupadas.add(int(str(ip_obj).split(".")[-1]))

        # Unimos ocupadas + reservadas
        bloqueadas = ocupadas | reserved_octets

        disponibles = []
        for host in range(start, end + 1):
            if host in bloqueadas:
                continue

            ip_candidate = ipaddress.ip_address(f"192.168.1.{host}")
            if ip_candidate in network:
                disponibles.append(str(ip_candidate))

        if limit is not None:
            disponibles = disponibles[:limit]

        return Response(
            {
                "subnet": str(network),
                "range": {"start": start, "end": end},
                "ocupadas_count": len(ocupadas),
                "reservadas_count": len(reserved_octets),
                "bloqueadas_count": len(bloqueadas),
                "disponibles_count": len(disponibles),
                "disponibles": disponibles,
                "ips_invalidas_en_db": invalidas[:50],
            },
            status=status.HTTP_200_OK
        )

