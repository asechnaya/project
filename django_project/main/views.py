from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse, Http404
from django.template import RequestContext, loader

from .models import *


def index(request):
    latest_documents_list = Document.objects.order_by('-date_of_creation')[:5]
    template = loader.get_template('polls/index.html')
    context = {
        'latest_documents_list': latest_documents_list
    }
    return HttpResponse(template.render(context))
    # return HttpResponse("Hello, world. You're at the polls index.")


def detail(request, document_id):
    try:
        document = get_object_or_404(Document, pk=document_id)
    except Document.DoesNotExist:
        raise Http404("Document does not exist!")
    return render(request, 'polls/detail.html', {'document': document})


# def detail(request, document_id):
#     return HttpResponse("You're looking at question %s." % document_id)


def results(request, document_id):
    response = "You're looking at the results of question %s."
    return HttpResponse(response % document_id)


def vote(request, document_id):
    return HttpResponse("You're voting on question %s." % document_id)
