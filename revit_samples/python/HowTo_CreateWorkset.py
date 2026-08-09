"""
Create a Workset
Creates a Workset - Revit 2017+

TESTED REVIT API: 2017

Author: Gui Talarico | github.com/gtalarico

This file is shared on www.revitapidocs.com
For more information visit http://github.com/gtalarico/revitapidocs
License: http://github.com/gtalarico/revitapidocs/blob/master/LICENSE.md
"""

import clr

clr.AddReference("RevitAPI")
from Autodesk.Revit.DB import Transaction, Workset

doc = __revit__.ActiveUIDocument.Document  # noqa: F821
# pyRevit runtime global — injected by the pyRevit loader at runtime.
# Fallback to None for static analysis / direct execution outside pyRevit.
try:
    __revit__  # type: ignore[used-before-def]  # noqa: F821
except NameError:
    __revit__ = None  # type: ignore[assignment]
doc = __revit__.ActiveUIDocument.Document


workset_name = "Point Clouds"
t = Transaction(doc)
t.Start("Create Workset")
Workset.Create(doc, workset_name)
t.Commit()
