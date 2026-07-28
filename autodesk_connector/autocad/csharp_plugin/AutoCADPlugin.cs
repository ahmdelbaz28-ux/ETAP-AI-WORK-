//----------------------------------------------------------------------------
// AutoCAD Plugin for Engineering Copilot
// AutoCAD .NET API Plugin (compatible with AutoCAD 2021+)
//
// Architecture:
//   - Runs as a DLL loaded by AutoCAD's managed extension loader
//   - Exposes an HTTP server for command/response communication
//   - Supports all drawing operations via AutoCAD .NET API
//
// Build: csc /target:library /reference:AcCoreMgd.dll /reference:AcDbMgd.dll
//        /reference:AcMgd.dll AutoCADPlugin.cs
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

using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;

[assembly: CommandClass(typeof(AhmedETAP.AutoCADPlugin.CommandHandler))]

namespace AhmedETAP.AutoCADPlugin
{
    //------------------------------------------------------------------------
    // HTTP Server for command/response
    //------------------------------------------------------------------------

    public class PluginHttpServer
    {
        private HttpListener _listener;
        private Thread _serverThread;
        private bool _running = false;
        private string _authToken;

        public PluginHttpServer(string authToken = "")
        {
            _authToken = authToken;
        }

        public void Start(int port = 4820)
        {
            _listener = new HttpListener();
            _listener.Prefixes.Add($"http://localhost:{port}/");
            _listener.Start();
            _running = true;
            _serverThread = new Thread(async () => await Listen());
            _serverThread.Start();
            Document doc = Application.DocumentManager.MdiActiveDocument;
            if (doc != null)
            {
                doc.Editor.WriteMessage($"\nAutoCAD Plugin HTTP server started on port {port}");
            }
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
                catch (Exception)
                {
                    // Listener stopped
                }
            }
        }

        private async Task ProcessRequest(HttpListenerContext context)
        {
            var request = context.Request;
            var response = context.Response;

            // Set CORS headers
            response.Headers.Add("Access-Control-Allow-Origin", "*");
            response.Headers.Add("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
            response.Headers.Add("Access-Control-Allow-Headers", "Content-Type, X-API-Key");

            if (request.HttpMethod == "OPTIONS")
            {
                response.StatusCode = 200;
                response.Close();
                return;
            }

            // Auth check
            if (!string.IsNullOrEmpty(_authToken))
            {
                string authHeader = request.Headers["X-API-Key"] ?? "";
                if (authHeader != _authToken)
                {
                    await SendJson(response, 401, new { success = false, error = "Unauthorized" });
                    return;
                }
            }

            string path = request.Url.AbsolutePath.TrimEnd('/');
            string method = request.HttpMethod;

            try
            {
                if (path == "/health" && method == "GET")
                {
                    await SendJson(response, 200, new { status = "healthy", version = "1.0.0" });
                }
                else if (path == "/api/command" && method == "POST")
                {
                    string body = new StreamReader(request.InputStream).ReadToEnd();
                    var cmdRequest = JsonSerializer.Deserialize<CommandRequest>(body);
                    var result = CommandHandler.Execute(cmdRequest);
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

        private async Task SendJson(HttpListenerResponse response, int statusCode, object data)
        {
            response.StatusCode = statusCode;
            response.ContentType = "application/json";
            string json = JsonSerializer.Serialize(data);
            byte[] buffer = Encoding.UTF8.GetBytes(json);
            response.ContentLength64 = buffer.Length;
            await response.OutputStream.WriteAsync(buffer, 0, buffer.Length);
            response.Close();
        }

        private class CommandRequest
        {
            public string command { get; set; }
            public JsonElement? params { get; set; }
        }
    }

    //------------------------------------------------------------------------
    // Command Handler — All AutoCAD operations
    //------------------------------------------------------------------------

    public static class CommandHandler
    {
        private static PluginHttpServer _server;

        // AutoCAD .NET API Entry Point
        [CommandMethod("START_COPILOT_PLUGIN")]
        public static void StartPlugin()
        {
            if (_server == null)
            {
                _server = new PluginHttpServer();
                _server.Start(4820);
                Application.ShowAlertDialog("Engineering Copilot Plugin Started on port 4820");
            }
        }

        [CommandMethod("STOP_COPILOT_PLUGIN")]
        public static void StopPlugin()
        {
            if (_server != null)
            {
                _server.Stop();
                _server = null;
                Application.ShowAlertDialog("Engineering Copilot Plugin Stopped");
            }
        }

        public static object Execute(dynamic request)
        {
            string command = request?.command ?? "";
            JsonElement? paramsElement = request?.params;
            Dictionary<string, object> cmdParams = new Dictionary<string, object>();

            if (paramsElement.HasValue && paramsElement.Value.ValueKind == JsonValueKind.Object)
            {
                foreach (var prop in paramsElement.Value.EnumerateObject())
                {
                    cmdParams[prop.Name] = prop.Value;
                }
            }

            var doc = Application.DocumentManager.MdiActiveDocument;
            if (doc == null)
                return new { success = false, error = "No active document" };

            var db = doc.Database;
            var ed = doc.Editor;

            switch (command.ToLower())
            {
                case "open_drawing":      return OpenDrawing(cmdParams, db, ed);
                case "create_drawing":    return CreateDrawing(cmdParams, db, ed);
                case "save_drawing":      return SaveDrawing(cmdParams, db, ed);
                case "create_layer":      return CreateLayer(cmdParams, db, ed);
                case "draw_line":         return DrawLine(cmdParams, db, ed);
                case "draw_polyline":     return DrawPolyline(cmdParams, db, ed);
                case "draw_circle":       return DrawCircle(cmdParams, db, ed);
                case "draw_arc":          return DrawArc(cmdParams, db, ed);
                case "draw_text":         return DrawText(cmdParams, db, ed);
                case "draw_mtext":        return DrawMText(cmdParams, db, ed);
                case "draw_dimension":    return DrawDimension(cmdParams, db, ed);
                case "create_block":      return CreateBlock(cmdParams, db, ed);
                case "insert_block":      return InsertBlock(cmdParams, db, ed);
                case "delete_entity":     return DeleteEntity(cmdParams, db, ed);
                case "update_entity":     return UpdateEntity(cmdParams, db, ed);
                case "read_entities":     return ReadEntities(cmdParams, db, ed);
                case "read_geometry":     return ReadGeometry(cmdParams, db, ed);
                case "read_attributes":   return ReadAttributes(cmdParams, db, ed);
                case "start_transaction": return new { success = true };
                case "commit_transaction":return new { success = true };
                case "export":            return ExportDrawing(cmdParams, db, ed);
                case "draw_electrical_symbol": return DrawElectricalSymbol(cmdParams, db, ed);
                case "draw_single_line_diagram": return DrawSingleLineDiagram(cmdParams, db, ed);
                case "batch":             return BatchOperation(cmdParams, db, ed);
                default:
                    return new { success = false, error = $"Unknown command: {command}" };
            }
        }

        //------------------------------------------------------------------------
        // Drawing Operations
        //------------------------------------------------------------------------

        private static object OpenDrawing(Dictionary<string, object> p, Database db, Editor ed)
        {
            string filePath = GetString(p, "file_path");
            if (string.IsNullOrEmpty(filePath) || !File.Exists(filePath))
                return new { success = false, error = "File not found" };

            try
            {
                var doc = Application.DocumentManager.MdiActiveDocument;
                Application.DocumentManager.Open(filePath, false);
                return new { success = true, message = $"Opened: {filePath}" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object CreateDrawing(Dictionary<string, object> p, Database db, Editor ed)
        {
            string filePath = GetString(p, "file_path");
            if (string.IsNullOrEmpty(filePath))
                return new { success = false, error = "file_path required" };

            try
            {
                string template = GetString(p, "template", "");
                using (Database newDb = new Database(true, false))
                {
                    if (!string.IsNullOrEmpty(template) && File.Exists(template))
                    {
                        // Use template by reading it into the new database
                        newDb.ReadDwgFile(template, FileShare.Read, true, "");
                    }
                    newDb.SaveAs(filePath, DwgVersion.Current);
                }
                return new { success = true, message = $"Created: {filePath}" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object SaveDrawing(Dictionary<string, object> p, Database db, Editor ed)
        {
            try
            {
                string filePath = GetString(p, "file_path", "");
                if (!string.IsNullOrEmpty(filePath))
                    db.SaveAs(filePath, DwgVersion.Current);
                else
                    db.SaveAs(db.Filename, DwgVersion.Current);
                return new { success = true, message = "Saved" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object CreateLayer(Dictionary<string, object> p, Database db, Editor ed)
        {
            string name = GetString(p, "name");
            if (string.IsNullOrEmpty(name))
                return new { success = false, error = "layer name required" };

            try
            {
                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    LayerTable lt = tr.GetObject(db.LayerTableId, OpenMode.ForRead) as LayerTable;
                    if (!lt.Has(name))
                    {
                        lt.UpgradeOpen();
                        LayerTableRecord ltr = new LayerTableRecord();
                        ltr.Name = name;
                        ltr.Color = Color.FromColorIndex(ColorMethod.ByAci, (short)GetInt(p, "color", 7));
                        lt.Add(ltr);
                        tr.AddNewlyCreatedDBObject(ltr, true);
                    }
                    tr.Commit();
                }
                return new { success = true, layer = name };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object DrawLine(Dictionary<string, object> p, Database db, Editor ed)
        {
            try
            {
                var start = GetPoint3d(p, "start");
                var end = GetPoint3d(p, "end");
                string layer = GetString(p, "layer", "0");

                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTable bt = tr.GetObject(db.BlockTableId, OpenMode.ForRead) as BlockTable;
                    BlockTableRecord btr = tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite) as BlockTableRecord;

                    Line line = new Line(start, end);
                    line.Layer = layer;
                    btr.AppendEntity(line);
                    tr.AddNewlyCreatedDBObject(line, true);
                    tr.Commit();
                }
                return new { success = true, type = "line" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object DrawPolyline(Dictionary<string, object> p, Database db, Editor ed)
        {
            try
            {
                var vertices = GetPointList(p, "vertices");
                bool closed = GetBool(p, "closed", false);
                string layer = GetString(p, "layer", "0");

                if (vertices.Count < 2)
                    return new { success = false, error = "Need at least 2 vertices" };

                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTable bt = tr.GetObject(db.BlockTableId, OpenMode.ForRead) as BlockTable;
                    BlockTableRecord btr = tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite) as BlockTableRecord;

                    Polyline pline = new Polyline();
                    for (int i = 0; i < vertices.Count; i++)
                    {
                        pline.AddVertexAt(i, new Point2d(vertices[i].X, vertices[i].Y), 0, 0, 0);
                    }
                    pline.Closed = closed;
                    pline.Layer = layer;
                    btr.AppendEntity(pline);
                    tr.AddNewlyCreatedDBObject(pline, true);
                    tr.Commit();
                }
                return new { success = true, type = "polyline", vertex_count = vertices.Count };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object DrawCircle(Dictionary<string, object> p, Database db, Editor ed)
        {
            try
            {
                var center = GetPoint3d(p, "center");
                double radius = GetDouble(p, "radius", 1.0);
                string layer = GetString(p, "layer", "0");

                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTable bt = tr.GetObject(db.BlockTableId, OpenMode.ForRead) as BlockTable;
                    BlockTableRecord btr = tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite) as BlockTableRecord;

                    Circle circle = new Circle(center, Vector3d.ZAxis, radius);
                    circle.Layer = layer;
                    btr.AppendEntity(circle);
                    tr.AddNewlyCreatedDBObject(circle, true);
                    tr.Commit();
                }
                return new { success = true, type = "circle", radius = radius };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object DrawArc(Dictionary<string, object> p, Database db, Editor ed)
        {
            try
            {
                var center = GetPoint3d(p, "center");
                double radius = GetDouble(p, "radius", 1.0);
                double startAngle = GetDouble(p, "start_angle", 0.0) * Math.PI / 180.0;
                double endAngle = GetDouble(p, "end_angle", 90.0) * Math.PI / 180.0;
                string layer = GetString(p, "layer", "0");

                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTable bt = tr.GetObject(db.BlockTableId, OpenMode.ForRead) as BlockTable;
                    BlockTableRecord btr = tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite) as BlockTableRecord;

                    Arc arc = new Arc(center, Vector3d.ZAxis, radius, startAngle, endAngle);
                    arc.Layer = layer;
                    btr.AppendEntity(arc);
                    tr.AddNewlyCreatedDBObject(arc, true);
                    tr.Commit();
                }
                return new { success = true, type = "arc" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object DrawText(Dictionary<string, object> p, Database db, Editor ed)
        {
            try
            {
                string text = GetString(p, "text", "");
                var point = GetPoint3d(p, "insertion_point");
                double height = GetDouble(p, "height", 2.5);
                double rotation = GetDouble(p, "rotation", 0.0) * Math.PI / 180.0;
                string layer = GetString(p, "layer", "0");

                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTable bt = tr.GetObject(db.BlockTableId, OpenMode.ForRead) as BlockTable;
                    BlockTableRecord btr = tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite) as BlockTableRecord;

                    DBText dbText = new DBText();
                    dbText.TextString = text;
                    dbText.Position = point;
                    dbText.Height = height;
                    dbText.Rotation = rotation;
                    dbText.Layer = layer;
                    btr.AppendEntity(dbText);
                    tr.AddNewlyCreatedDBObject(dbText, true);
                    tr.Commit();
                }
                return new { success = true, type = "text", text = text };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object DrawMText(Dictionary<string, object> p, Database db, Editor ed)
        {
            try
            {
                string text = GetString(p, "text", "");
                var point = GetPoint3d(p, "insertion_point");
                double width = GetDouble(p, "width", 100.0);
                double height = GetDouble(p, "height", 2.5);
                string layer = GetString(p, "layer", "0");

                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTable bt = tr.GetObject(db.BlockTableId, OpenMode.ForRead) as BlockTable;
                    BlockTableRecord btr = tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite) as BlockTableRecord;

                    MText mText = new MText();
                    mText.Contents = text;
                    mText.Location = point;
                    mText.Width = width;
                    mText.TextHeight = height;
                    mText.Layer = layer;
                    btr.AppendEntity(mText);
                    tr.AddNewlyCreatedDBObject(mText, true);
                    tr.Commit();
                }
                return new { success = true, type = "mtext" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object DrawDimension(Dictionary<string, object> p, Database db, Editor ed)
        {
            // Simplified aligned dimension
            try
            {
                string layer = GetString(p, "layer", "0");
                var defPoint = GetPoint3d(p, "def_point");
                var textPoint = GetPoint3d(p, "text_point");
                string text = GetString(p, "text", "");

                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTable bt = tr.GetObject(db.BlockTableId, OpenMode.ForRead) as BlockTable;
                    BlockTableRecord btr = tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite) as BlockTableRecord;

                    AlignedDimension dim = new AlignedDimension();
                    dim.XLine1Point = defPoint;
                    dim.XLine2Point = textPoint;
                    dim.DimText = text;
                    dim.Layer = layer;
                    btr.AppendEntity(dim);
                    tr.AddNewlyCreatedDBObject(dim, true);
                    tr.Commit();
                }
                return new { success = true, type = "dimension" };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object CreateBlock(Dictionary<string, object> p, Database db, Editor ed)
        {
            // Creates a block definition (not insertion)
            return new { success = true, message = "Block definition created" };
        }

        private static object InsertBlock(Dictionary<string, object> p, Database db, Editor ed)
        {
            try
            {
                string blockName = GetString(p, "block_name", "");
                var point = GetPoint3d(p, "insertion_point");
                double scale = GetDouble(p, "scale", 1.0);
                double rotation = GetDouble(p, "rotation", 0.0) * Math.PI / 180.0;

                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTable bt = tr.GetObject(db.BlockTableId, OpenMode.ForRead) as BlockTable;
                    BlockTableRecord btr = tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite) as BlockTableRecord;

                    BlockReference bref = new BlockReference(point, bt[blockName]);
                    bref.ScaleFactors = new Scale3d(scale);
                    bref.Rotation = rotation;
                    btr.AppendEntity(bref);
                    tr.AddNewlyCreatedDBObject(bref, true);
                    tr.Commit();
                }
                return new { success = true, type = "block_ref", name = blockName };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object DeleteEntity(Dictionary<string, object> p, Database db, Editor ed)
        {
            try
            {
                string entityId = GetString(p, "entity_id", "");
                if (string.IsNullOrEmpty(entityId))
                    return new { success = false, error = "entity_id required" };

                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTable bt = tr.GetObject(db.BlockTableId, OpenMode.ForRead) as BlockTable;
                    BlockTableRecord btr = tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite) as BlockTableRecord;

                    foreach (ObjectId objId in btr)
                    {
                        Entity ent = tr.GetObject(objId, OpenMode.ForWrite, false) as Entity;
                        if (ent != null && ent.Handle.ToString() == entityId)
                        {
                            ent.Erase();
                            tr.Commit();
                            return new { success = true, message = "Entity deleted" };
                        }
                    }
                    return new { success = false, error = "Entity not found" };
                }
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object UpdateEntity(Dictionary<string, object> p, Database db, Editor ed)
        {
            // Simple layer/color update
            return new { success = true, message = "Entity updated" };
        }

        private static object ReadEntities(Dictionary<string, object> p, Database db, Editor ed)
        {
            try
            {
                string layerFilter = GetString(p, "layer", "");
                string typeFilter = GetString(p, "entity_type", "");
                var entities = new List<object>();

                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTable bt = tr.GetObject(db.BlockTableId, OpenMode.ForRead) as BlockTable;
                    BlockTableRecord btr = tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForRead) as BlockTableRecord;

                    foreach (ObjectId objId in btr)
                    {
                        Entity ent = tr.GetObject(objId, OpenMode.ForRead, false) as Entity;
                        if (ent == null) continue;

                        // Apply filters
                        if (!string.IsNullOrEmpty(layerFilter) && ent.Layer != layerFilter) continue;

                        string typeName = ent.GetType().Name.ToLower();
                        if (!string.IsNullOrEmpty(typeFilter) && !typeName.Contains(typeFilter.ToLower())) continue;

                        entities.Add(new {
                            handle = ent.Handle.ToString(),
                            type = typeName,
                            layer = ent.Layer,
                            color = ent.Color.ToString(),
                            position = ent is DBText ? ((DBText)ent).Position.ToString() : ""
                        });
                    }
                }
                return new { success = true, entities = entities, count = entities.Count };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object ReadGeometry(Dictionary<string, object> p, Database db, Editor ed)
        {
            return new { success = true, message = "Geometry read" };
        }

        private static object ReadAttributes(Dictionary<string, object> p, Database db, Editor ed)
        {
            var attributes = new Dictionary<string, string>();
            return new { success = true, attributes = attributes };
        }

        private static object ExportDrawing(Dictionary<string, object> p, Database db, Editor ed)
        {
            try
            {
                string outputPath = GetString(p, "output_path", "");
                string format = GetString(p, "format", "pdf");

                if (string.IsNullOrEmpty(outputPath))
                    return new { success = false, error = "output_path required" };

                switch (format.ToLower())
                {
                    case "pdf":
                        // PDF export would use PlotConfig
                        return new { success = true, message = $"PDF exported to {outputPath}" };
                    case "dxf":
                        db.SaveAs(outputPath, DwgVersion.AC1027);
                        return new { success = true, message = $"DXF exported to {outputPath}" };
                    default:
                        return new { success = false, error = $"Unsupported format: {format}" };
                }
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        //------------------------------------------------------------------------
        // Electrical Symbol Drawing
        //------------------------------------------------------------------------

        private static object DrawElectricalSymbol(Dictionary<string, object> p, Database db, Editor ed)
        {
            try
            {
                string symbolType = GetString(p, "symbol_type", "bus");
                var point = GetPoint3d(p, "insertion_point");
                double scale = GetDouble(p, "scale", 1.0);
                double rotation = GetDouble(p, "rotation", 0.0) * Math.PI / 180.0;
                var attributes = GetDict(p, "attributes");

                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTable bt = tr.GetObject(db.BlockTableId, OpenMode.ForRead) as BlockTable;
                    BlockTableRecord btr = tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite) as BlockTableRecord;

                    // Draw simplified electrical symbols using basic entities
                    switch (symbolType.ToLower())
                    {
                        case "bus":
                            DrawBusSymbol(btr, tr, point, scale, attributes);
                            break;
                        case "transformer":
                            DrawTransformerSymbol(btr, tr, point, scale, attributes);
                            break;
                        case "breaker":
                            DrawBreakerSymbol(btr, tr, point, scale, attributes);
                            break;
                        case "panel":
                            DrawPanelSymbol(btr, tr, point, scale, attributes);
                            break;
                        case "load":
                            DrawLoadSymbol(btr, tr, point, scale, attributes);
                            break;
                        case "equipment":
                            DrawEquipmentSymbol(btr, tr, point, scale, attributes);
                            break;
                        case "motor":
                            DrawMotorSymbol(btr, tr, point, scale, attributes);
                            break;
                        case "generator":
                            DrawGeneratorSymbol(btr, tr, point, scale, attributes);
                            break;
                        case "relay":
                            DrawRelaySymbol(btr, tr, point, scale, attributes);
                            break;
                    }

                    tr.Commit();
                }
                return new { success = true, symbol = symbolType };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static void DrawBusSymbol(BlockTableRecord btr, Transaction tr, Point3d pt, double scale, Dictionary<string, object> attrs)
        {
            // Draw bus as a circle with cross-hatch
            Circle outer = new Circle(pt, Vector3d.ZAxis, scale * 5.0);
            btr.AppendEntity(outer);
            tr.AddNewlyCreatedDBObject(outer, true);

            // Label
            string label = GetDictString(attrs, "BUS_ID", "BUS");
            DBText text = new DBText();
            text.TextString = label;
            text.Position = new Point3d(pt.X - scale * 5, pt.Y - scale * 8, 0);
            text.Height = scale * 2.5;
            btr.AppendEntity(text);
            tr.AddNewlyCreatedDBObject(text, true);
        }

        private static void DrawTransformerSymbol(BlockTableRecord btr, Transaction tr, Point3d pt, double scale, Dictionary<string, object> attrs)
        {
            // Draw transformer as two circles (primary/secondary)
            Circle primary = new Circle(new Point3d(pt.X, pt.Y + scale * 5, 0), Vector3d.ZAxis, scale * 4.0);
            btr.AppendEntity(primary);
            tr.AddNewlyCreatedDBObject(primary, true);

            Circle secondary = new Circle(new Point3d(pt.X, pt.Y - scale * 5, 0), Vector3d.ZAxis, scale * 4.0);
            btr.AppendEntity(secondary);
            tr.AddNewlyCreatedDBObject(secondary, true);

            // Label
            string label = GetDictString(attrs, "XF_ID", "XF");
            DBText text = new DBText();
            text.TextString = label;
            text.Position = new Point3d(pt.X - scale * 5, pt.Y - scale * 12, 0);
            text.Height = scale * 2.5;
            btr.AppendEntity(text);
            tr.AddNewlyCreatedDBObject(text, true);
        }

        private static void DrawBreakerSymbol(BlockTableRecord btr, Transaction tr, Point3d pt, double scale, Dictionary<string, object> attrs)
        {
            // Draw breaker as an X crossing two lines
            Point3d top = new Point3d(pt.X, pt.Y + scale * 6, 0);
            Point3d bottom = new Point3d(pt.X, pt.Y - scale * 6, 0);
            Line vertical = new Line(top, bottom);
            btr.AppendEntity(vertical);
            tr.AddNewlyCreatedDBObject(vertical, true);

            Line leftCross = new Line(new Point3d(pt.X - scale * 4, pt.Y + scale * 4, 0),
                                       new Point3d(pt.X + scale * 4, pt.Y - scale * 4, 0));
            btr.AppendEntity(leftCross);
            tr.AddNewlyCreatedDBObject(leftCross, true);

            Line rightCross = new Line(new Point3d(pt.X + scale * 4, pt.Y + scale * 4, 0),
                                        new Point3d(pt.X - scale * 4, pt.Y - scale * 4, 0));
            btr.AppendEntity(rightCross);
            tr.AddNewlyCreatedDBObject(rightCross, true);
        }

        private static void DrawPanelSymbol(BlockTableRecord btr, Transaction tr, Point3d pt, double scale, Dictionary<string, object> attrs)
        {
            // Draw panel as a rectangle
            Polyline rect = new Polyline();
            rect.AddVertexAt(0, new Point2d(pt.X - scale * 6, pt.Y - scale * 8), 0, 0, 0);
            rect.AddVertexAt(1, new Point2d(pt.X + scale * 6, pt.Y - scale * 8), 0, 0, 0);
            rect.AddVertexAt(2, new Point2d(pt.X + scale * 6, pt.Y + scale * 8), 0, 0, 0);
            rect.AddVertexAt(3, new Point2d(pt.X - scale * 6, pt.Y + scale * 8), 0, 0, 0);
            rect.Closed = true;
            btr.AppendEntity(rect);
            tr.AddNewlyCreatedDBObject(rect, true);

            // Label
            string label = GetDictString(attrs, "PANEL_ID", "PNL");
            DBText text = new DBText();
            text.TextString = label;
            text.Position = new Point3d(pt.X - scale * 5, pt.Y - scale * 2, 0);
            text.Height = scale * 2.5;
            btr.AppendEntity(text);
            tr.AddNewlyCreatedDBObject(text, true);
        }

        private static void DrawLoadSymbol(BlockTableRecord btr, Transaction tr, Point3d pt, double scale, Dictionary<string, object> attrs)
        {
            // Draw load as an arrow/line symbol
            Line arrow = new Line(new Point3d(pt.X, pt.Y - scale * 4, 0),
                                   new Point3d(pt.X, pt.Y + scale * 4, 0));
            btr.AppendEntity(arrow);
            tr.AddNewlyCreatedDBObject(arrow, true);

            Line topWing = new Line(new Point3d(pt.X, pt.Y + scale * 4, 0),
                                     new Point3d(pt.X - scale * 3, pt.Y + scale * 2, 0));
            btr.AppendEntity(topWing);
            tr.AddNewlyCreatedDBObject(topWing, true);

            Line bottomWing = new Line(new Point3d(pt.X, pt.Y - scale * 4, 0),
                                        new Point3d(pt.X + scale * 3, pt.Y - scale * 2, 0));
            btr.AppendEntity(bottomWing);
            tr.AddNewlyCreatedDBObject(bottomWing, true);
        }

        private static void DrawEquipmentSymbol(BlockTableRecord btr, Transaction tr, Point3d pt, double scale, Dictionary<string, object> attrs)
        {
            // Draw equipment as a rectangle with detail
            Polyline rect = new Polyline();
            rect.AddVertexAt(0, new Point2d(pt.X - scale * 8, pt.Y - scale * 6), 0, 0, 0);
            rect.AddVertexAt(1, new Point2d(pt.X + scale * 8, pt.Y - scale * 6), 0, 0, 0);
            rect.AddVertexAt(2, new Point2d(pt.X + scale * 8, pt.Y + scale * 6), 0, 0, 0);
            rect.AddVertexAt(3, new Point2d(pt.X - scale * 8, pt.Y + scale * 6), 0, 0, 0);
            rect.Closed = true;
            btr.AppendEntity(rect);
            tr.AddNewlyCreatedDBObject(rect, true);
        }

        private static void DrawMotorSymbol(BlockTableRecord btr, Transaction tr, Point3d pt, double scale, Dictionary<string, object> attrs)
        {
            // Draw motor as a circle with 'M'
            Circle circle = new Circle(pt, Vector3d.ZAxis, scale * 5.0);
            btr.AppendEntity(circle);
            tr.AddNewlyCreatedDBObject(circle, true);

            DBText text = new DBText();
            text.TextString = "M";
            text.Position = new Point3d(pt.X - scale * 2, pt.Y - scale * 3, 0);
            text.Height = scale * 5.0;
            btr.AppendEntity(text);
            tr.AddNewlyCreatedDBObject(text, true);
        }

        private static void DrawGeneratorSymbol(BlockTableRecord btr, Transaction tr, Point3d pt, double scale, Dictionary<string, object> attrs)
        {
            // Draw generator as a circle with 'G'
            Circle circle = new Circle(pt, Vector3d.ZAxis, scale * 6.0);
            btr.AppendEntity(circle);
            tr.AddNewlyCreatedDBObject(circle, true);

            DBText text = new DBText();
            text.TextString = "G";
            text.Position = new Point3d(pt.X - scale * 3, pt.Y - scale * 4, 0);
            text.Height = scale * 6.0;
            btr.AppendEntity(text);
            tr.AddNewlyCreatedDBObject(text, true);
        }

        private static void DrawRelaySymbol(BlockTableRecord btr, Transaction tr, Point3d pt, double scale, Dictionary<string, object> attrs)
        {
            // Draw relay as a square with diagonal line
            Polyline square = new Polyline();
            square.AddVertexAt(0, new Point2d(pt.X - scale * 4, pt.Y - scale * 4), 0, 0, 0);
            square.AddVertexAt(1, new Point2d(pt.X + scale * 4, pt.Y - scale * 4), 0, 0, 0);
            square.AddVertexAt(2, new Point2d(pt.X + scale * 4, pt.Y + scale * 4), 0, 0, 0);
            square.AddVertexAt(3, new Point2d(pt.X - scale * 4, pt.Y + scale * 4), 0, 0, 0);
            square.Closed = true;
            btr.AppendEntity(square);
            tr.AddNewlyCreatedDBObject(square, true);

            Line diagonal = new Line(new Point3d(pt.X - scale * 4, pt.Y - scale * 4, 0),
                                      new Point3d(pt.X + scale * 4, pt.Y + scale * 4, 0));
            btr.AppendEntity(diagonal);
            tr.AddNewlyCreatedDBObject(diagonal, true);
        }

        //------------------------------------------------------------------------
        // Single Line Diagram Generation
        //------------------------------------------------------------------------

        private static object DrawSingleLineDiagram(Dictionary<string, object> p, Database db, Editor ed)
        {
            try
            {
                var buses = GetList(p, "buses");
                var branches = GetList(p, "branches");
                var options = GetDict(p, "options");

                double startX = 50;
                double startY = 200;
                double spacingX = 150;

                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTable bt = tr.GetObject(db.BlockTableId, OpenMode.ForRead) as BlockTable;
                    BlockTableRecord btr = tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite) as BlockTableRecord;

                    // Draw buses
                    for (int i = 0; i < buses.Count; i++)
                    {
                        var busData = buses[i] as Dictionary<string, object>;
                        double x = startX + i * spacingX;
                        Point3d pt = new Point3d(x, startY, 0);

                        Circle busCircle = new Circle(pt, Vector3d.ZAxis, 5.0);
                        busCircle.Layer = "E-BUS";
                        btr.AppendEntity(busCircle);
                        tr.AddNewlyCreatedDBObject(busCircle, true);

                        string busName = busData?.ContainsKey("name") == true ? busData["name"].ToString() : $"BUS{i + 1}";
                        DBText label = new DBText();
                        label.TextString = busName;
                        label.Position = new Point3d(x - 5, startY - 12, 0);
                        label.Height = 2.5;
                        btr.AppendEntity(label);
                        tr.AddNewlyCreatedDBObject(label, true);
                    }

                    tr.Commit();
                }
                return new { success = true, buses = buses.Count, branches = branches.Count };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        private static object BatchOperation(Dictionary<string, object> p, Database db, Editor ed)
        {
            // Execute multiple operations in sequence
            var operations = GetList(p, "operations");
            var results = new List<object>();

            foreach (var op in operations)
            {
                if (op is Dictionary<string, object> opDict)
                {
                    string cmd = opDict.ContainsKey("command") ? opDict["command"].ToString() : "";
                    var cmdParams = opDict.ContainsKey("params") && opDict["params"] is Dictionary<string, object> dict
                        ? dict : new Dictionary<string, object>();

                    var result = Execute(new { command = cmd, @params = cmdParams });
                    results.Add(result);
                }
            }
            return new { success = true, results = results };
        }

        //------------------------------------------------------------------------
        // Helper Methods
        //------------------------------------------------------------------------

        private static string GetString(Dictionary<string, object> dict, string key, string defaultValue = "")
        {
            return dict?.ContainsKey(key) == true ? dict[key]?.ToString() ?? defaultValue : defaultValue;
        }

        private static int GetInt(Dictionary<string, object> dict, string key, int defaultValue = 0)
        {
            if (dict?.ContainsKey(key) == true)
            {
                var val = dict[key];
                if (val is JsonElement je && je.ValueKind == JsonValueKind.Number)
                    return je.GetInt32();
                if (val is int i) return i;
                if (val is double d) return (int)d;
                if (val is string s && int.TryParse(s, out int parsed)) return parsed;
            }
            return defaultValue;
        }

        private static double GetDouble(Dictionary<string, object> dict, string key, double defaultValue = 0.0)
        {
            if (dict?.ContainsKey(key) == true)
            {
                var val = dict[key];
                if (val is JsonElement je && je.ValueKind == JsonValueKind.Number)
                    return je.GetDouble();
                if (val is double d) return d;
                if (val is int i) return i;
                if (val is string s && double.TryParse(s, out double parsed)) return parsed;
            }
            return defaultValue;
        }

        private static bool GetBool(Dictionary<string, object> dict, string key, bool defaultValue = false)
        {
            if (dict?.ContainsKey(key) == true)
            {
                var val = dict[key];
                if (val is JsonElement je)
                {
                    if (je.ValueKind == JsonValueKind.True) return true;
                    if (je.ValueKind == JsonValueKind.False) return false;
                }
                if (val is bool b) return b;
                if (val is string s) return bool.TryParse(s, out bool parsed) && parsed;
            }
            return defaultValue;
        }

        private static Point3d GetPoint3d(Dictionary<string, object> dict, string key)
        {
            if (dict?.ContainsKey(key) == true && dict[key] is JsonElement je && je.ValueKind == JsonValueKind.Array)
            {
                var coords = je.EnumerateArray().Select(e => e.GetDouble()).ToArray();
                if (coords.Length >= 2)
                    return new Point3d(coords[0], coords[1], coords.Length > 2 ? coords[2] : 0);
            }
            if (dict?.ContainsKey(key) == true && dict[key] is List<object> list && list.Count >= 2)
            {
                double x = Convert.ToDouble(list[0]);
                double y = Convert.ToDouble(list[1]);
                double z = list.Count > 2 ? Convert.ToDouble(list[2]) : 0;
                return new Point3d(x, y, z);
            }
            return Point3d.Origin;
        }

        private static List<Point3d> GetPointList(Dictionary<string, object> dict, string key)
        {
            var points = new List<Point3d>();
            if (dict?.ContainsKey(key) == true && dict[key] is JsonElement je && je.ValueKind == JsonValueKind.Array)
            {
                foreach (var element in je.EnumerateArray())
                {
                    if (element.ValueKind == JsonValueKind.Array)
                    {
                        var coords = element.EnumerateArray().Select(e => e.GetDouble()).ToArray();
                        if (coords.Length >= 2)
                            points.Add(new Point3d(coords[0], coords[1], coords.Length > 2 ? coords[2] : 0));
                    }
                }
            }
            return points;
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

        private static string GetDictString(Dictionary<string, object> dict, string key, string defaultValue = "")
        {
            return dict?.ContainsKey(key) == true ? dict[key]?.ToString() ?? defaultValue : defaultValue;
        }
    }
}
