/// <reference types="vite/client" />

declare module "*.json" {
  const value: Record<string, unknown>;
  export default value;
}

// lucide-react v0.468.0 ships without bundled .d.ts declarations.
// The package.json specifies "typings": "dist/lucide-react.d.ts" but the file
// is not included in the npm tarball. This ambient declaration provides type
// safety for all icon imports.
declare module "lucide-react" {
  import type { FC, SVGProps } from "react";

  export type IconNode = [element: string, attrs: Record<string, string>][];
  export type Icon = FC<SVGProps<SVGSVGElement>>;

  export const createLucideIcon: (name: string, iconNode: IconNode) => Icon;

  // Navigation
  export const ChevronDown: Icon;
  export const ChevronUp: Icon;
  export const ChevronLeft: Icon;
  export const ChevronRight: Icon;
  export const ChevronsLeft: Icon;
  export const ChevronsRight: Icon;
  export const Menu: Icon;
  export const X: Icon;
  export const Plus: Icon;
  export const Minus: Icon;
  export const MoreHorizontal: Icon;
  export const MoreVertical: Icon;
  export const ExternalLink: Icon;
  export const Maximize2: Icon;
  export const Minimize2: Icon;
  export const Expand: Icon;
  export const Collapse: Icon;

  // Actions
  export const Search: Icon;
  export const Filter: Icon;
  export const SortAsc: Icon;
  export const SortDesc: Icon;
  export const RefreshCw: Icon;
  export const Download: Icon;
  export const Upload: Icon;
  export const Save: Icon;
  export const Edit: Icon;
  export const Edit3: Icon;
  export const Trash2: Icon;
  export const Trash: Icon;
  export const Copy: Icon;
  export const Clipboard: Icon;
  export const ClipboardList: Icon;
  export const Send: Icon;
  export const Share2: Icon;
  export const Link: Icon;
  export const Unlink: Icon;
  export const Undo: Icon;
  export const Redo: Icon;
  export const Play: Icon;
  export const Pause: Icon;
  export const StopCircle: Icon;
  export const Settings: Icon;
  export const LogOut: Icon;
  export const LogIn: Icon;
  export const UserPlus: Icon;
  export const UserMinus: Icon;
  export const Ban: Icon;
  export const Check: Icon;
  export const CheckCircle: Icon;
  export const CheckCircle2: Icon;
  export const AlertCircle: Icon;
  export const AlertTriangle: Icon;
  export const Info: Icon;
  export const HelpCircle: Icon;
  export const Loader2: Icon;
  export const Spinner: Icon;

  // Files & Docs
  export const File: Icon;
  export const FileText: Icon;
  export const FileSpreadsheet: Icon;
  export const Folder: Icon;
  export const FolderOpen: Icon;
  export const FolderPlus: Icon;
  export const Database: Icon;
  export const HardDrive: Icon;

  // Charts & Data
  export const BarChart3: Icon;
  export const BarChart4: Icon;
  export const LineChart: Icon;
  export const PieChart: Icon;
  export const Activity: Icon;
  export const TrendingUp: Icon;
  export const TrendingDown: Icon;
  export const Gauge: Icon;

  // Status & Alerts
  export const Bell: Icon;
  export const BellOff: Icon;
  export const Shield: Icon;
  export const ShieldOff: Icon;
  export const Lock: Icon;
  export const Unlock: Icon;
  export const Key: Icon;
  export const Eye: Icon;
  export const EyeOff: Icon;
  export const Wifi: Icon;
  export const WifiOff: Icon;
  export const Signal: Icon;
  export const SignalHigh: Icon;
  export const SignalMedium: Icon;
  export const SignalLow: Icon;
  export const Zap: Icon;
  export const ZapOff: Icon;

  // Layout
  export const Grid: Icon;
  export const Grid3X3: Icon;
  export const Columns: Icon;
  export const Rows: Icon;
  export const Layout: Icon;
  export const LayoutDashboard: Icon;
  export const PanelLeft: Icon;
  export const PanelRight: Icon;
  export const PanelTop: Icon;
  export const PanelBottom: Icon;
  export const Maximize: Icon;
  export const Sidebar: Icon;

  // Media
  export const Image: Icon;
  export const Camera: Icon;
  export const Video: Icon;
  export const Monitor: Icon;
  export const Tablet: Icon;
  export const Smartphone: Icon;

  // Objects
  export const Box: Icon;
  export const Package: Icon;
  export const Archive: Icon;
  export const BookOpen: Icon;
  export const Bookmark: Icon;
  export const Tag: Icon;
  export const Tags: Icon;
  export const Globe: Icon;
  // biome-ignore lint/suspicious/noShadowRestrictedNames: lucide-react icon export
  export const Map: Icon;
  export const MapPin: Icon;
  export const Compass: Icon;
  export const Home: Icon;
  export const Building: Icon;
  export const Building2: Icon;

  // Communication
  export const Mail: Icon;
  export const Phone: Icon;
  export const MessageSquare: Icon;
  export const MessageCircle: Icon;
  export const Inbox: Icon;

  // Users
  export const User: Icon;
  export const Users: Icon;
  export const UserCheck: Icon;
  export const UserX: Icon;
  export const UserCircle: Icon;
  export const UserCircle2: Icon;
  export const Avatar: Icon;

  // Weather
  export const Sun: Icon;
  export const Moon: Icon;
  export const Cloud: Icon;
  export const CloudSun: Icon;
  export const CloudMoon: Icon;
  export const CloudRain: Icon;
  export const CloudLightning: Icon;
  export const CloudSnow: Icon;
  export const CloudDrizzle: Icon;
  export const CloudFog: Icon;
  export const Wind: Icon;
  export const Umbrella: Icon;
  export const Thermometer: Icon;

  // Arrows
  export const ArrowUp: Icon;
  export const ArrowDown: Icon;
  export const ArrowLeft: Icon;
  export const ArrowRight: Icon;
  export const ArrowUpDown: Icon;
  export const ArrowUpCircle: Icon;
  export const ArrowDownCircle: Icon;
  export const ArrowLeftCircle: Icon;
  export const ArrowRightCircle: Icon;
  export const ArrowUpRight: Icon;
  export const ArrowDownLeft: Icon;
  export const ArrowDownRight: Icon;
  export const Move: Icon;
  export const MoveHorizontal: Icon;
  export const MoveVertical: Icon;

  // Misc
  export const Sliders: Icon;
  export const SlidersHorizontal: Icon;
  export const ToggleLeft: Icon;
  export const ToggleRight: Icon;
  export const List: Icon;
  export const ListOrdered: Icon;
  export const ListChecks: Icon;
  export const Hash: Icon;
  export const AtSign: Icon;
  export const DollarSign: Icon;
  export const Percent: Icon;
  export const Clock: Icon;
  export const Calendar: Icon;
  export const CalendarDays: Icon;
  export const Timer: Icon;
  export const Stopwatch: Icon;
  export const Heart: Icon;
  export const Star: Icon;
  export const Award: Icon;
  export const Trophy: Icon;
  export const Gift: Icon;
  export const Flag: Icon;
  export const FlagTriangleRight: Icon;
  export const Target: Icon;
  export const Crosshair: Icon;
  export const Focus: Icon;
  export const Scan: Icon;
  export const ScanLine: Icon;
  export const Circle: Icon;
  export const Square: Icon;
  export const Triangle: Icon;
  export const Hexagon: Icon;
  export const Octagon: Icon;
  export const Diamond: Icon;
  export const Palette: Icon;
  export const Paintbrush: Icon;
  export const Eyedropper: Icon;
  export const Eraser: Icon;
  export const Type: Icon;
  export const Bold: Icon;
  export const Italic: Icon;
  export const Underline: Icon;
  export const Code: Icon;
  export const Code2: Icon;
  export const Terminal: Icon;
  export const Command: Icon;
  export const Cpu: Icon;
  export const Server: Icon;
  export const CloudOff: Icon;
  export const Power: Icon;
  export const PowerOff: Icon;
  export const Battery: Icon;
  export const BatteryCharging: Icon;
  export const BatteryFull: Icon;
  export const BatteryMedium: Icon;
  export const BatteryLow: Icon;
  export const Printer: Icon;
  export const MousePointer: Icon;
  export const MousePointerClick: Icon;
  export const Hand: Icon;
  export const Volume: Icon;
  export const Volume2: Icon;
  export const VolumeX: Icon;
  export const Mic: Icon;
  export const MicOff: Icon;
  export const Headphones: Icon;
  export const Radio: Icon;
  export const Rss: Icon;
  export const Repeat: Icon;
  export const Shuffle: Icon;
  export const FastForward: Icon;
  export const Rewind: Icon;
  export const SkipForward: Icon;
  export const SkipBack: Icon;
  export const Sparkles: Icon;
  export const ShieldCheck: Icon;
  export const ShieldAlert: Icon;
  export const FlaskConical: Icon;
  export const Bot: Icon;
  export const Layers: Icon;
  export const Bug: Icon;
  export const ScrollText: Icon;
  export const Navigation: Icon;
  export const CornerDownLeft: Icon;
  export const FileQuestion: Icon;
  export const GripVertical: Icon;
  export const PanelLeftClose: Icon;
  export const PanelRightClose: Icon;
  export const FolderKanban: Icon;
  export const Plug: Icon;
  export const Network: Icon;
  export const Wrench: Icon;
  export const Keyboard: Icon;
  export const Cable: Icon;
  export const TestTube: Icon;
  export const FileJson: Icon;
  export const CloudUpload: Icon;
  export const Beaker: Icon;
  export const RotateCcw: Icon;
  export const Table: Icon;
  export const XCircle: Icon;
  export const Settings2: Icon;
  export const Link2: Icon;
  export type LucideIcon = Icon;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  export const createElement: any;
}
