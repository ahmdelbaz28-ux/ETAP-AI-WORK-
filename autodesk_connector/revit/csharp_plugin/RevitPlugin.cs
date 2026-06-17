//----------------------------------------------------------------------------
// Revit Plugin for Engineering Copilot
// Revit API Plugin (compatible with Revit 2022+)
//
// Architecture:
//   - Runs as a DLL loaded by Revit's Add-In Manager
//   - Exposes an HTTP server for command/response communication
//   - Supports all BIM operations via Revit API
//
// Build: csc /target:library /reference:RevitAPI.dll /reference:RevitAPIUI.dll
//        RevitPlugin.cs
//----------------------------------------------------------------------------

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

using Autodesk.Revit.ApplicationServices;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Architecture;
using Autodesk.Revit.DB.Electrical;
using Autodesk.Revit.DB.Mechanical;
using Autodesk.Revit.DB.Plumbing;
using Autodesk.Revit.UI;

[assembly: RegenerationOption(RegenerationOption.Manual)]

namespace AhmedETAP.RevitPlugin
{
    //------------------------------------------------------------------------
    // External Application Entry Point
    //------------------------------------------------------------------------

    public class CopilotRevitApp : IExternalApplication
    {
        private static PluginHttpServer _server;

        public Result OnStartup(UIControlledApplication application)
        {
            _server = new PluginHttpServer(application);
            _server.Start(4830);
            TaskDialog.Show("Engineering Copilot",
                "Revit Plugin started on port 4830");
            return Result.Succeeded;
        }

        public Result OnShutdown(UIControlledApplication application)
        {
            _server?.Stop();
            return Result.Succeeded;
        }

        public static PluginHttpServer GetServer() => _server;
    }

    //------------------------------------------------------------------------
    // HTTP Server
    //------------------------------------------------------------------------

    public class PluginHttpServer
    {
        private HttpListener _listener;
        private Thread _serverThread;
        private bool _running = false;
        private UIControlledApplication _uiApp;

        public PluginHttpServer(UIControlledApplication uiApp)
        {
            _uiApp = uiApp;
        }

        public void Start(int port = 4830)
        {
            _listener = new HttpListener();
            _listener.Prefixes.Add($"http://localhost:{port}/");
            _listener.Start();
            _running = true;
            _serverThread = new Thread(async () => await Listen());
            _serverThread.Start();
        }

        public void Stop()
        {
            _running = false;
            _listener?.Stop();
        }

        private async Task Listen()
        {
            while (_running)
            {
                try
                {
                    var context = await _listener.GetContextAsync();
                    await ProcessRequest(context);
                }
                catch (Exception) { }
            }
        }

        private async Task ProcessRequest(HttpListenerContext context)
        {
            var request = context.Request;
            var response = context.Response;

            response.Headers.Add("Access-Control-Allow-Origin", "*");
            response.Headers.Add("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
            response.Headers.Add("Access-Control-Allow-Headers", "Content-Type, X-API-Key");

            if (request.HttpMethod == "OPTIONS")
            {
                response.StatusCode = 200;
                response.Close();
                return;
            }

            string path = request.Url.AbsolutePath.TrimEnd('/');
            string method = request.HttpMethod;

            try
            {
                if (path == "/health" && method == "GET")
                {
                    await SendJson(response, 200, new { status = "healthy", version = "1.0.0" });
                }
                else if (path.StartsWith("/api/") && method == "POST")
                {
                    string body = new StreamReader(request.InputStream).ReadToEnd();
                    var payload = JsonSerializer.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();

                    // Execute on Revit's main thread via ExternalEvent
                    var result = ExecuteOnRevitThread(path, payload);
                    await SendJson(response, 200, result);
                }
                else
                {
                    await SendJson(response, 404, new { success = false, error = "Not found" });
                }
            }
            catch (Exception ex)
            {
                await SendJson(response, 500, new { success = false, error = ex.Message });
            }
        }

        private object ExecuteOnRevitThread(string path, Dictionary<string, object> payload)
        {
            // Revit API must be called from the main thread.
            // For simplicity, we use the active UIApplication.
            try
            {
                UIApplication uiApp = _uiApp?.ControlledApplication?.IsValidProductActive == true
                    ? null
                    : null;

                // Fallback: use the current Revit UIApplication
                var doc = Autodesk.Revit.ApplicationServices.Application
                    .GetFirstDocument();

                return CommandHandler.Execute(path, payload);
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private async Task SendJson(HttpListenerResponse response, int statusCode, object data)
        {
            response.StatusCode = statusCode;
            response.ContentType = "application/json";
            string json = JsonSerializer.Serialize(data, new JsonSerializerOptions
            {
                WriteIndented = true,
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase
            });
            byte[] buffer = Encoding.UTF8.GetBytes(json);
            response.ContentLength64 = buffer.Length;
            await response.OutputStream.WriteAsync(buffer, 0, buffer.Length);
            response.Close();
        }
    }

    //------------------------------------------------------------------------
    // Command Handler
    //------------------------------------------------------------------------

    public static class CommandHandler
    {
        private static UIApplication _uiApp;

        public static void SetUIApplication(UIApplication app)
        {
            _uiApp = app;
        }

        public static object Execute(string path, Dictionary<string, object> payload)
        {
            var uiApp = _uiApp;
            if (uiApp == null)
            {
                // Try to get from the active Revit session
                return new { success = false, error = "No active Revit session" };
            }

            var doc = uiApp.ActiveUIDocument?.Document;
            if (doc == null)
                return new { success = false, error = "No active document" };

            // Route to appropriate handler based on path
            switch (path)
            {
                // Model operations
                case "/api/model/open":         return OpenModel(payload, doc);
                case "/api/model/save":         return SaveModel(payload, doc);
                case "/api/model/create":       return CreateModel(payload, doc, uiApp);

                // Element operations
                case "/api/element/create":     return CreateElement(payload, doc);
                case "/api/element/update":     return UpdateElement(payload, doc);
                case "/api/element/delete":     return DeleteElement(payload, doc);
                case "/api/element/read":       return ReadElement(payload, doc);
                case "/api/element/list":       return ListElements(payload, doc);

                // Family operations
                case "/api/family/load":        return LoadFamily(payload, doc);
                case "/api/family/place":       return PlaceFamily(payload, doc, uiApp);
                case "/api/family/list":        return ListFamilies(payload, doc);

                // Parameter operations
                case "/api/parameter/read":     return ReadParameters(payload, doc);
                case "/api/parameter/update":   return UpdateParameter(payload, doc);

                // Level & Room operations
                case "/api/level/create":       return CreateLevel(payload, doc);
                case "/api/level/list":         return ListLevels(payload, doc);
                case "/api/room/create":        return CreateRoom(payload, doc);
                case "/api/room/list":          return ListRooms(payload, doc);

                // MEP operations
                case "/api/mep/electrical_systems": return ReadElectricalSystems(payload, doc);
                case "/api/mep/data":               return ReadMepData(payload, doc);
                case "/api/mep/create_circuit":      return CreateCircuit(payload, doc);

                // Sync operations
                case "/api/sync/to_model":      return SyncToModel(payload, doc);
                case "/api/sync/from_model":    return SyncFromModel(payload, doc);
                case "/api/documentation/generate": return GenerateDocumentation(payload, doc);

                default:
                    return new { success = false, error = $"Unknown endpoint: {path}" };
            }
        }

        //------------------------------------------------------------------------
        // Model Operations
        //------------------------------------------------------------------------

        private static object OpenModel(Dictionary<string, object> p, Document doc)
        {
            string filePath = GetString(p, "file_path");
            if (string.IsNullOrEmpty(filePath) || !File.Exists(filePath))
                return new { success = false, error = "File not found" };

            try
            {
                var uiApp = _uiApp;
                if (uiApp != null)
                {
                    var newDoc = uiApp.Application.OpenDocumentFile(filePath);
                    return new { success = true, message = $"Opened: {filePath}" };
                }
                return new { success = false, error = "Cannot open model from this context" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object SaveModel(Dictionary<string, object> p, Document doc)
        {
            try
            {
                string filePath = GetString(p, "file_path");
                if (!string.IsNullOrEmpty(filePath))
                {
                    SaveAsOptions opts = new SaveAsOptions { OverwriteExistingFile = true };
                    doc.SaveAs(filePath, opts);
                }
                else
                {
                    doc.Save();
                }
                return new { success = true, message = "Model saved" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object CreateModel(Dictionary<string, object> p, Document doc, UIApplication uiApp)
        {
            string filePath = GetString(p, "file_path");
            string template = GetString(p, "template", "");

            try
            {
                if (!string.IsNullOrEmpty(template))
                {
                    var newDoc = uiApp.Application.NewProjectFromTemplate(template);
                    return new { success = true, message = $"Created from template: {template}" };
                }
                else
                {
                    var newDoc = uiApp.Application.NewProjectDocument(UnitSystem.Metric);
                    return new { success = true, message = "New empty model created" };
                }
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        //------------------------------------------------------------------------
        // Element Operations
        //------------------------------------------------------------------------

        private static object CreateElement(Dictionary<string, object> p, Document doc)
        {
            try
            {
                string elementType = GetString(p, "element_type", "");
                var parameters = GetDict(p, "parameters");
                var location = GetList(p, "location");
                string levelId = GetString(p, "level_id", "");

                using (Transaction tx = new Transaction(doc, "Create Element"))
                {
                    tx.Start();

                    Element created = null;

                    switch (elementType.ToLower())
                    {
                        case "panel":
                        case "panelboard":
                            created = CreatePanelElement(doc, parameters, location);
                            break;
                        case "electrical_equipment":
                            created = CreateElectricalEquipment(doc, parameters, location);
                            break;
                        case "transformer":
                            created = CreateElectricalEquipment(doc, parameters, location);
                            break;
                        case "cable_tray":
                            created = CreateCableTray(doc, parameters);
                            break;
                        case "conduit":
                            created = CreateConduit(doc, parameters);
                            break;
                        default:
                            tx.RollBack();
                            return new { success = false, error = $"Unknown element type: {elementType}" };
                    }

                    if (created != null)
                    {
                        tx.Commit();
                        return new { success = true, element_id = created.Id.ToString(), type = elementType };
                    }

                    tx.RollBack();
                    return new { success = false, error = "Failed to create element" };
                }
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static Element CreatePanelElement(Document doc, Dictionary<string, object> p, List<object> location)
        {
            // Find Electrical Equipment category and panel family
            FilteredElementCollector collector = new FilteredElementCollector(doc);
            var familySymbols = collector
                .OfClass(typeof(FamilySymbol))
                .OfCategory(BuiltInCategory.OST_ElectricalEquipment)
                .Cast<FamilySymbol>()
                .Where(f => f.FamilyName != null && f.FamilyName.ToLower().Contains("panel"))
                .ToList();

            FamilySymbol symbol = familySymbols.FirstOrDefault();
            if (symbol == null)
            {
                // Create at project origin if no symbol found
                symbol = collector
                    .OfClass(typeof(FamilySymbol))
                    .OfCategory(BuiltInCategory.OST_ElectricalEquipment)
                    .FirstElement() as FamilySymbol;
            }

            if (symbol == null)
                return null;

            if (!symbol.IsActive)
                symbol.Activate();

            double x = location.Count > 0 ? Convert.ToDouble(location[0]) : 0;
            double y = location.Count > 1 ? Convert.ToDouble(location[1]) : 0;
            double z = location.Count > 2 ? Convert.ToDouble(location[2]) : 0;

            XYZ point = new XYZ(x, y, z);
            FamilyInstance instance = doc.Create.NewFamilyInstance(point, symbol, Autodesk.Revit.DB.Structure.StructuralType.NonStructural);

            // Set parameters
            if (p.ContainsKey("panel_name"))
                SetParameter(instance, "Panel Name", p["panel_name"].ToString());
            if (p.ContainsKey("voltage_v"))
                SetParameter(instance, "Voltage", Convert.ToDouble(p["voltage_v"]));
            if (p.ContainsKey("main_rating_a"))
                SetParameter(instance, "Main Rating", Convert.ToDouble(p["main_rating_a"]));

            return instance;
        }

        private static Element CreateElectricalEquipment(Document doc, Dictionary<string, object> p, List<object> location)
        {
            FilteredElementCollector collector = new FilteredElementCollector(doc);
            var symbols = collector
                .OfClass(typeof(FamilySymbol))
                .OfCategory(BuiltInCategory.OST_ElectricalEquipment)
                .Cast<FamilySymbol>()
                .ToList();

            var symbol = symbols.FirstOrDefault();
            if (symbol == null) return null;

            if (!symbol.IsActive)
                symbol.Activate();

            double x = location.Count > 0 ? Convert.ToDouble(location[0]) : 0;
            double y = location.Count > 1 ? Convert.ToDouble(location[1]) : 0;
            double z = location.Count > 2 ? Convert.ToDouble(location[2]) : 0;

            XYZ point = new XYZ(x, y, z);
            return doc.Create.NewFamilyInstance(point, symbol, Autodesk.Revit.DB.Structure.StructuralType.NonStructural);
        }

        private static Element CreateCableTray(Document doc, Dictionary<string, object> p)
        {
            // Create cable tray using MEP API
            double width_mm = GetDouble(p, "width_mm", 300);
            double height_mm = GetDouble(p, "height_mm", 100);

            // Find cable tray type
            FilteredElementCollector collector = new FilteredElementCollector(doc);
            var trayTypes = collector
                .OfClass(typeof(CableTrayType))
                .Cast<CableTrayType>()
                .ToList();

            var trayType = trayTypes.FirstOrDefault();
            if (trayType == null) return null;

            // Create a simple horizontal run
            XYZ start = new XYZ(0, 0, 3000); // 3m elevation
            XYZ end = new XYZ(10000, 0, 3000); // 10m run

            var curve = Line.CreateBound(start, end);
            var tray = CableTray.Create(doc, trayType.Id, curve, start);

            return tray;
        }

        private static Element CreateConduit(Document doc, Dictionary<string, object> p)
        {
            double diameter_mm = GetDouble(p, "diameter_mm", 20);

            FilteredElementCollector collector = new FilteredElementCollector(doc);
            var conduitTypes = collector
                .OfClass(typeof(ConduitType))
                .Cast<ConduitType>()
                .ToList();

            var conduitType = conduitTypes.FirstOrDefault();
            if (conduitType == null) return null;

            XYZ start = new XYZ(0, 0, 3000);
            XYZ end = new XYZ(5000, 0, 3000);

            var curve = Line.CreateBound(start, end);
            var conduit = Conduit.Create(doc, conduitType.Id, curve, start);

            return conduit;
        }

        private static object UpdateElement(Dictionary<string, object> p, Document doc)
        {
            string elementId = GetString(p, "element_id", "");
            var parameters = GetDict(p, "parameters");

            if (string.IsNullOrEmpty(elementId))
                return new { success = false, error = "element_id required" };

            try
            {
                ElementId id = new ElementId(Convert.ToInt32(elementId));
                Element element = doc.GetElement(id);
                if (element == null)
                    return new { success = false, error = "Element not found" };

                using (Transaction tx = new Transaction(doc, "Update Element"))
                {
                    tx.Start();
                    foreach (var kvp in parameters)
                    {
                        SetParameter(element, kvp.Key, kvp.Value?.ToString() ?? "");
                    }
                    tx.Commit();
                }
                return new { success = true, message = "Element updated" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object DeleteElement(Dictionary<string, object> p, Document doc)
        {
            string elementId = GetString(p, "element_id", "");

            if (string.IsNullOrEmpty(elementId))
                return new { success = false, error = "element_id required" };

            try
            {
                ElementId id = new ElementId(Convert.ToInt32(elementId));
                using (Transaction tx = new Transaction(doc, "Delete Element"))
                {
                    tx.Start();
                    doc.Delete(id);
                    tx.Commit();
                }
                return new { success = true, message = "Element deleted" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object ReadElement(Dictionary<string, object> p, Document doc)
        {
            string elementId = GetString(p, "element_id", "");
            if (string.IsNullOrEmpty(elementId))
                return new { success = false, error = "element_id required" };

            try
            {
                ElementId id = new ElementId(Convert.ToInt32(elementId));
                Element element = doc.GetElement(id);
                if (element == null)
                    return new { success = false, error = "Element not found" };

                var parameters = new Dictionary<string, string>();
                foreach (Parameter param in element.Parameters)
                {
                    if (param.HasValue)
                        parameters[param.Definition?.Name ?? ""] = param.AsValueString() ?? param.AsString() ?? "";
                }

                return new
                {
                    success = true,
                    element = new
                    {
                        id = element.Id.ToString(),
                        name = element.Name,
                        category = element.Category?.Name ?? "",
                        location = element.Location?.ToString() ?? "",
                        parameters = parameters
                    }
                };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object ListElements(Dictionary<string, object> p, Document doc)
        {
            string category = GetString(p, "category", "");
            string levelId = GetString(p, "level_id", "");

            try
            {
                var elements = new List<object>();

                FilteredElementCollector collector = new FilteredElementCollector(doc);
                var allElements = collector.WhereElementIsNotElementType().ToElements();

                foreach (Element e in allElements)
                {
                    if (!string.IsNullOrEmpty(category) && e.Category?.Name != category) continue;
                    if (!string.IsNullOrEmpty(levelId))
                    {
                        var levelParam = e.get_Parameter(BuiltInParameter.LEVEL_PARAM);
                        if (levelParam == null || levelParam.AsElementId().ToString() != levelId) continue;
                    }

                    elements.Add(new
                    {
                        id = e.Id.ToString(),
                        name = e.Name,
                        category = e.Category?.Name ?? "",
                        type = e.GetType().Name
                    });

                    if (elements.Count >= 1000) break;
                }

                return new { success = true, elements = elements, count = elements.Count };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        //------------------------------------------------------------------------
        // Family Operations
        //------------------------------------------------------------------------

        private static object LoadFamily(Dictionary<string, object> p, Document doc)
        {
            string familyPath = GetString(p, "family_path", "");
            if (string.IsNullOrEmpty(familyPath) || !File.Exists(familyPath))
                return new { success = false, error = "Family file not found" };

            try
            {
                using (Transaction tx = new Transaction(doc, "Load Family"))
                {
                    tx.Start();
                    doc.LoadFamily(familyPath, new FamilyLoadOptions());
                    tx.Commit();
                }
                return new { success = true, message = $"Family loaded: {familyPath}" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object PlaceFamily(Dictionary<string, object> p, Document doc, UIApplication uiApp)
        {
            string familySymbol = GetString(p, "family_symbol", "");
            var insertionPoint = GetList(p, "insertion_point");
            string levelId = GetString(p, "level_id", "");

            if (string.IsNullOrEmpty(familySymbol))
                return new { success = false, error = "family_symbol required" };

            try
            {
                FilteredElementCollector collector = new FilteredElementCollector(doc);
                var symbol = collector
                    .OfClass(typeof(FamilySymbol))
                    .Cast<FamilySymbol>()
                    .FirstOrDefault(f => f.Name == familySymbol || f.FamilyName == familySymbol);

                if (symbol == null)
                    return new { success = false, error = $"Family symbol not found: {familySymbol}" };

                if (!symbol.IsActive)
                {
                    using (Transaction tx = new Transaction(doc, "Activate Symbol"))
                    {
                        tx.Start();
                        symbol.Activate();
                        tx.Commit();
                    }
                }

                double x = insertionPoint.Count > 0 ? Convert.ToDouble(insertionPoint[0]) : 0;
                double y = insertionPoint.Count > 1 ? Convert.ToDouble(insertionPoint[1]) : 0;
                double z = insertionPoint.Count > 2 ? Convert.ToDouble(insertionPoint[2]) : 0;

                using (Transaction tx = new Transaction(doc, "Place Family"))
                {
                    tx.Start();
                    XYZ point = new XYZ(x, y, z);
                    FamilyInstance instance = doc.Create.NewFamilyInstance(
                        point, symbol, Autodesk.Revit.DB.Structure.StructuralType.NonStructural);
                    tx.Commit();

                    return new { success = true, element_id = instance.Id.ToString(), family = familySymbol };
                }
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object ListFamilies(Dictionary<string, object> p, Document doc)
        {
            string category = GetString(p, "category", "");
            var families = new List<object>();

            FilteredElementCollector collector = new FilteredElementCollector(doc);
            var familySymbols = collector
                .OfClass(typeof(FamilySymbol))
                .Cast<FamilySymbol>()
                .ToList();

            var grouped = familySymbols
                .GroupBy(f => f.FamilyName)
                .Select(g => new
                {
                    family_name = g.Key,
                    category = g.First().Category?.Name ?? "",
                    symbols = g.Select(s => s.Name).ToList()
                });

            return new { success = true, families = grouped, count = familySymbols.Count() };
        }

        //------------------------------------------------------------------------
        // Parameter Operations
        //------------------------------------------------------------------------

        private static object ReadParameters(Dictionary<string, object> p, Document doc)
        {
            string elementId = GetString(p, "element_id", "");
            if (string.IsNullOrEmpty(elementId))
                return new { success = false, error = "element_id required" };

            try
            {
                ElementId id = new ElementId(Convert.ToInt32(elementId));
                Element element = doc.GetElement(id);
                if (element == null)
                    return new { success = false, error = "Element not found" };

                var parameters = new Dictionary<string, object>();
                foreach (Parameter param in element.Parameters)
                {
                    if (param.HasValue && param.Definition != null)
                    {
                        string name = param.Definition.Name;
                        parameters[name] = param.AsValueString() ?? param.AsString() ?? param.AsInteger().ToString();
                    }
                }

                return new { success = true, element_id = elementId, parameters = parameters, count = parameters.Count };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object UpdateParameter(Dictionary<string, object> p, Document doc)
        {
            string elementId = GetString(p, "element_id", "");
            string paramName = GetString(p, "param_name", "");
            object value = p.ContainsKey("value") ? p["value"] : null;

            if (string.IsNullOrEmpty(elementId) || string.IsNullOrEmpty(paramName) || value == null)
                return new { success = false, error = "element_id, param_name, and value required" };

            try
            {
                ElementId id = new ElementId(Convert.ToInt32(elementId));
                Element element = doc.GetElement(id);
                if (element == null)
                    return new { success = false, error = "Element not found" };

                using (Transaction tx = new Transaction(doc, "Update Parameter"))
                {
                    tx.Start();
                    bool updated = SetParameter(element, paramName, value.ToString());
                    tx.Commit();

                    return new { success = updated, message = updated ? "Parameter updated" : "Parameter not found" };
                }
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        //------------------------------------------------------------------------
        // Level & Room Operations
        //------------------------------------------------------------------------

        private static object CreateLevel(Dictionary<string, object> p, Document doc)
        {
            string name = GetString(p, "name", "Level 1");
            double elevation = GetDouble(p, "elevation", 0.0);

            try
            {
                using (Transaction tx = new Transaction(doc, "Create Level"))
                {
                    tx.Start();

                    Level level = Level.Create(doc, elevation);
                    level.Name = name;

                    tx.Commit();
                    return new { success = true, level_id = level.Id.ToString(), name = name, elevation = elevation };
                }
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object ListLevels(Dictionary<string, object> p, Document doc)
        {
            try
            {
                FilteredElementCollector collector = new FilteredElementCollector(doc);
                var levels = collector
                    .OfClass(typeof(Level))
                    .Cast<Level>()
                    .Select(l => new
                    {
                        id = l.Id.ToString(),
                        name = l.Name,
                        elevation = l.Elevation
                    })
                    .ToList();

                return new { success = true, levels = levels, count = levels.Count };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object CreateRoom(Dictionary<string, object> p, Document doc)
        {
            string name = GetString(p, "name", "Room");
            string levelId = GetString(p, "level_id", "");
            var boundingBox = GetDict(p, "bounding_box");

            try
            {
                Level level = null;
                if (!string.IsNullOrEmpty(levelId))
                {
                    ElementId id = new ElementId(Convert.ToInt32(levelId));
                    level = doc.GetElement(id) as Level;
                }

                if (level == null)
                {
                    FilteredElementCollector collector = new FilteredElementCollector(doc);
                    level = collector.OfClass(typeof(Level)).Cast<Level>().FirstOrDefault();
                }

                if (level == null)
                    return new { success = false, error = "No level found" };

                using (Transaction tx = new Transaction(doc, "Create Room"))
                {
                    tx.Start();

                    XYZ pt = new XYZ(0, 0, 0);
                    Room room = doc.Create.NewRoom(level, pt);
                    room.Name = name;

                    tx.Commit();
                    return new { success = true, room_id = room.Id.ToString(), name = name };
                }
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object ListRooms(Dictionary<string, object> p, Document doc)
        {
            try
            {
                string levelId = GetString(p, "level_id", "");

                FilteredElementCollector collector = new FilteredElementCollector(doc);
                var rooms = collector
                    .OfCategory(BuiltInCategory.OST_Rooms)
                    .OfClass(typeof(SpatialElement))
                    .Cast<Room>()
                    .Select(r => new
                    {
                        id = r.Id.ToString(),
                        name = r.Name,
                        area = r.Area,
                        volume = r.Volume,
                        level_id = r.Level?.Id.ToString() ?? ""
                    })
                    .ToList();

                if (!string.IsNullOrEmpty(levelId))
                    rooms = rooms.Where(r => r.level_id == levelId).ToList();

                return new { success = true, rooms = rooms, count = rooms.Count };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        //------------------------------------------------------------------------
        // MEP Operations
        //------------------------------------------------------------------------

        private static object ReadElectricalSystems(Dictionary<string, object> p, Document doc)
        {
            try
            {
                var systems = new List<object>();

                FilteredElementCollector collector = new FilteredElementCollector(doc);
                var elecSystems = collector
                    .OfClass(typeof(ElectricalSystem))
                    .Cast<ElectricalSystem>()
                    .ToList();

                foreach (var sys in elecSystems.Take(100))
                {
                    var panel = sys.BaseEquipment;
                    systems.Add(new
                    {
                        id = sys.Id.ToString(),
                        name = sys.Name,
                        panel_name = panel?.Name ?? "",
                        panel_id = panel?.Id.ToString() ?? "",
                        load_kw = Math.Round(sys.Load, 3),
                        voltage = sys.Voltage,
                        circuit_number = sys.CircuitNumber,
                        phase_count = (int)sys.Phase
                    });
                }

                return new { success = true, systems = systems, count = systems.Count };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object ReadMepData(Dictionary<string, object> p, Document doc)
        {
            try
            {
                var mepData = new Dictionary<string, object>();

                // Electrical equipment
                var elecEquip = new FilteredElementCollector(doc)
                    .OfCategory(BuiltInCategory.OST_ElectricalEquipment)
                    .WhereElementIsNotElementType()
                    .Count();
                mepData["electrical_equipment_count"] = elecEquip;

                // Lighting fixtures
                var lights = new FilteredElementCollector(doc)
                    .OfCategory(BuiltInCategory.OST_LightingFixtures)
                    .WhereElementIsNotElementType()
                    .Count();
                mepData["lighting_fixtures_count"] = lights;

                // Cable trays
                var trays = new FilteredElementCollector(doc)
                    .OfClass(typeof(CableTray))
                    .Count();
                mepData["cable_trays_count"] = trays;

                // Conduits
                var conduits = new FilteredElementCollector(doc)
                    .OfClass(typeof(Conduit))
                    .Count();
                mepData["conduits_count"] = conduits;

                // Electrical systems
                var systems = new FilteredElementCollector(doc)
                    .OfClass(typeof(ElectricalSystem))
                    .Count();
                mepData["electrical_systems_count"] = systems;

                return new { success = true, mep_data = mepData };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object CreateCircuit(Dictionary<string, object> p, Document doc)
        {
            string panelId = GetString(p, "panel_id", "");
            var deviceIds = GetList(p, "device_ids");
            int? circuitNumber = p.ContainsKey("circuit_number") ? Convert.ToInt32(p["circuit_number"]) : (int?)null;

            if (string.IsNullOrEmpty(panelId) || deviceIds.Count == 0)
                return new { success = false, error = "panel_id and device_ids required" };

            try
            {
                ElementId panelElemId = new ElementId(Convert.ToInt32(panelId));
                FamilyInstance panel = doc.GetElement(panelElemId) as FamilyInstance;
                if (panel == null)
                    return new { success = false, error = "Panel not found" };

                var devices = new List<FamilyInstance>();
                foreach (var devId in deviceIds)
                {
                    ElementId devElemId = new ElementId(Convert.ToInt32(devId.ToString()));
                    FamilyInstance device = doc.GetElement(devElemId) as FamilyInstance;
                    if (device != null)
                        devices.Add(device);
                }

                if (devices.Count == 0)
                    return new { success = false, error = "No valid devices found" };

                using (Transaction tx = new Transaction(doc, "Create Circuit"))
                {
                    tx.Start();

                    ElectricalSystem circuit = ElectricalSystem.Create(doc, devices, panel);
                    if (circuitNumber.HasValue)
                        circuit.CircuitNumber = circuitNumber.Value;

                    tx.Commit();
                    return new
                    {
                        success = true,
                        circuit_id = circuit.Id.ToString(),
                        circuit_number = circuit.CircuitNumber,
                        devices = devices.Count
                    };
                }
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        //------------------------------------------------------------------------
        // Sync Operations
        //------------------------------------------------------------------------

        private static object SyncToModel(Dictionary<string, object> p, Document doc)
        {
            try
            {
                var model = new
                {
                    levels = ListLevelsBody(doc),
                    rooms = ListRoomsBody(doc),
                    electrical_elements = ListElectricalElementsBody(doc),
                    mep_equipment = ListMepEquipmentBody(doc)
                };

                string json = JsonSerializer.Serialize(model, new JsonSerializerOptions
                {
                    WriteIndented = true,
                    PropertyNamingPolicy = JsonNamingPolicy.CamelCase
                });

                return new { success = true, model_json = json };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object SyncFromModel(Dictionary<string, object> p, Document doc)
        {
            string modelJson = GetString(p, "model_json", "");
            if (string.IsNullOrEmpty(modelJson))
                return new { success = false, error = "model_json required" };

            try
            {
                // Parse and import model
                using (Transaction tx = new Transaction(doc, "Sync from Model"))
                {
                    tx.Start();

                    // Create levels, rooms, and equipment based on model data
                    // This is a stub that would parse the JSON and create elements

                    tx.Commit();
                }
                return new { success = true, message = "Model imported" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object GenerateDocumentation(Dictionary<string, object> p, Document doc)
        {
            try
            {
                var panels = new List<object>();

                var collector = new FilteredElementCollector(doc);
                var elecEquipment = collector
                    .OfCategory(BuiltInCategory.OST_ElectricalEquipment)
                    .WhereElementIsNotElementType()
                    .ToElements();

                foreach (Element eq in elecEquipment)
                {
                    var panelParam = eq.get_Parameter(BuiltInParameter.RBS_ELEC_PANEL_NAME);
                    var ratingParam = eq.get_Parameter(BuiltInParameter.RBS_ELEC_MAIN_RATING);

                    panels.Add(new
                    {
                        id = eq.Id.ToString(),
                        name = eq.Name,
                        panel_name = panelParam?.AsString() ?? "",
                        main_rating = ratingParam?.AsInteger() ?? 0
                    });
                }

                return new { success = true, panels = panels, count = panels.Count };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        //------------------------------------------------------------------------
        // Helper Methods
        //------------------------------------------------------------------------

        private static string GetString(Dictionary<string, object> dict, string key, string defaultValue = "")
        {
            return dict?.ContainsKey(key) == true ? dict[key]?.ToString() ?? defaultValue : defaultValue;
        }

        private static double GetDouble(Dictionary<string, object> dict, string key, double defaultValue = 0.0)
        {
            if (dict?.ContainsKey(key) == true)
            {
                var val = dict[key];
                if (val is double d) return d;
                if (val is int i) return i;
                if (val is JsonElement je && je.ValueKind == JsonValueKind.Number) return je.GetDouble();
                if (val is string s && double.TryParse(s, out double parsed)) return parsed;
            }
            return defaultValue;
        }

        private static bool GetBool(Dictionary<string, object> dict, string key, bool defaultValue = false)
        {
            if (dict?.ContainsKey(key) == true)
            {
                var val = dict[key];
                if (val is bool b) return b;
                if (val is JsonElement je) return je.ValueKind == JsonValueKind.True;
                if (val is string s) return bool.TryParse(s, out bool parsed) && parsed;
            }
            return defaultValue;
        }

        private static List<object> GetList(Dictionary<string, object> dict, string key)
        {
            if (dict?.ContainsKey(key) == true && dict[key] is List<object> list)
                return list;
            return new List<object>();
        }

        private static Dictionary<string, object> GetDict(Dictionary<string, object> dict, string key)
        {
            if (dict?.ContainsKey(key) == true && dict[key] is Dictionary<string, object> innerDict)
                return innerDict;
            return new Dictionary<string, object>();
        }

        private static bool SetParameter(Element element, string paramName, object value)
        {
            foreach (Parameter param in element.Parameters)
            {
                if (param.Definition?.Name == paramName || param.Definition?.ParameterGroup.ToString() == paramName)
                {
                    switch (param.StorageType)
                    {
                        case StorageType.String:
                            param.Set(value?.ToString() ?? "");
                            return true;
                        case StorageType.Integer:
                            if (value is int iVal) { param.Set(iVal); return true; }
                            if (value is double dVal) { param.Set((int)dVal); return true; }
                            if (int.TryParse(value?.ToString(), out int parsed)) { param.Set(parsed); return true; }
                            return false;
                        case StorageType.Double:
                            if (value is double dVal2) { param.Set(dVal2); return true; }
                            if (value is int iVal2) { param.Set((double)iVal2); return true; }
                            if (double.TryParse(value?.ToString(), out double parsed2)) { param.Set(parsed2); return true; }
                            return false;
                    }
                    return false;
                }
            }
            return false;
        }

        private static List<object> ListLevelsBody(Document doc)
        {
            var levels = new List<object>();
            var collector = new FilteredElementCollector(doc);
            foreach (Level l in collector.OfClass(typeof(Level)).Cast<Level>())
            {
                levels.Add(new { id = l.Id.ToString(), name = l.Name, elevation = l.Elevation });
            }
            return levels;
        }

        private static List<object> ListRoomsBody(Document doc)
        {
            var rooms = new List<object>();
            var collector = new FilteredElementCollector(doc);
            foreach (Room r in collector.OfCategory(BuiltInCategory.OST_Rooms).OfClass(typeof(SpatialElement)).Cast<Room>())
            {
                rooms.Add(new { id = r.Id.ToString(), name = r.Name, area = r.Area, level_id = r.Level?.Id.ToString() ?? "" });
            }
            return rooms;
        }

        private static List<object> ListElectricalElementsBody(Document doc)
        {
            var elements = new List<object>();
            var collector = new FilteredElementCollector(doc);
            foreach (Element e in collector.OfCategory(BuiltInCategory.OST_ElectricalEquipment).WhereElementIsNotElementType())
            {
                elements.Add(new { id = e.Id.ToString(), name = e.Name, category = e.Category?.Name ?? "" });
            }
            return elements;
        }

        private static List<object> ListMepEquipmentBody(Document doc)
        {
            var equipment = new List<object>();
            var collector = new FilteredElementCollector(doc);
            foreach (Element e in collector.OfCategory(BuiltInCategory.OST_MechanicalEquipment).WhereElementIsNotElementType())
            {
                equipment.Add(new { id = e.Id.ToString(), name = e.Name });
            }
            return equipment;
        }
    }

    //------------------------------------------------------------------------
    // Family Load Options
    //------------------------------------------------------------------------

    public class FamilyLoadOptions : IFamilyLoadOptions
    {
        public bool OnFamilyFound(bool familyInUse, out bool overwriteParameterValues)
        {
            overwriteParameterValues = true;
            return true;
        }

        public bool OnSharedFamilyFound(Family sharedFamily, bool familyInUse, out bool overwriteParameterValues)
        {
            overwriteParameterValues = true;
            return true;
        }
    }
}
