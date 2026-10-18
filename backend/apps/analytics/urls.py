from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.OverviewView.as_view(), name="analytics-overview"),
    path("ticket-trends/", views.TicketTrendsView.as_view(), name="analytics-trends"),
    path("category-breakdown/", views.CategoryBreakdownView.as_view(), name="analytics-categories"),
    path("resolution-time/", views.ResolutionTimeView.as_view(), name="analytics-resolution"),
    path("sla/", views.SLAView.as_view(), name="analytics-sla"),
    path("agent-workload/", views.AgentWorkloadView.as_view(), name="analytics-workload"),
]
