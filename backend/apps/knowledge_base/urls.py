from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ArticleSearchView, ArticleViewSet, AskKnowledgeBaseView

router = DefaultRouter(trailing_slash=True)
router.include_root_view = False
router.register("articles", ArticleViewSet, basename="kb-article")

urlpatterns = [
    path("search/", ArticleSearchView.as_view(), name="kb-search"),
    path("ask/", AskKnowledgeBaseView.as_view(), name="kb-ask"),
    *router.urls,
]
