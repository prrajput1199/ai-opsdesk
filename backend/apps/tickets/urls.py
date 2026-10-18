from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, SLAPolicyViewSet, TicketViewSet

router = DefaultRouter(trailing_slash=True)
router.include_root_view = False
router.register("tickets", TicketViewSet, basename="ticket")
router.register("categories", CategoryViewSet, basename="category")
router.register("sla-policies", SLAPolicyViewSet, basename="sla-policy")

urlpatterns = router.urls
