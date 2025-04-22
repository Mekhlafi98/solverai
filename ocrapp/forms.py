from django import forms

class PDFUploadForm(forms.Form):
    file = forms.FileField(label='Upload a PDF', required=True)
