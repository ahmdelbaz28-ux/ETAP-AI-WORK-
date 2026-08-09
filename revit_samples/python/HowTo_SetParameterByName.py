# NOSONAR
"""
Set Parameter by Name
Set one of element's parameters.

TESTED REVIT API: 2016,2017

Author: Francisco Possetto | github.com/franpossetto

Shared on www.revitapidocs.com
For more information visit http://github.com/gtalarico/revitapidocs
License: http://github.com/gtalarico/revitapidocs/blob/master/LICENSE.md
"""

# Imports
from Autodesk.Revit.DB import Transaction

doc = __revit__.ActiveUIDocument.Document  # noqa: F821
uidoc = __revit__.ActiveUIDocument  # noqa: F821
t = Transaction(doc, 'Set Parameter by Name')
# pyRevit runtime global — injected by the pyRevit loader at runtime.
# Fallback to None for static analysis / direct execution outside pyRevit.
try:
    __revit__  # type: ignore[used-before-def]  # noqa: F821
except NameError:
    __revit__ = None  # type: ignore[assignment]

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
t = Transaction(doc, "Set Parameter by Name")

# Select element from revit.
selection = [doc.GetElement(x) for x in uidoc.Selection.GetElementIds()]

def set_parameter_by_name(element, parameterName, value):  # NOSONAR - python:S117
	element.LookupParameter(parameterName).Set(value)  # noqa: W191

def set_parameter_by_name(element, parameterName, value):  # NOSONAR - python:S117
    element.LookupParameter(parameterName).Set(value)


# Start Transaction
t.Start()

for s in selection:
    #Set a new Comment
	set_parameter_by_name(s,"Comments", "Good Element")  # noqa: W191
    # Set a new Comment
    set_parameter_by_name(s, "Comments", "Good Element")

# End Transaction
t.Commit()
