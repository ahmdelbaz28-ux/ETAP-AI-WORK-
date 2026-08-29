// Augment lucide-react module to include icons that exist at runtime in
// v0.468 but TypeScript under verbatimModuleSyntax cannot verify them from
// the barrel export. Add new icons here as needed.
declare module "lucide-react" {
  export const Cog: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const Flame: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const CalendarClock: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const PlayCircle: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const GitBranch: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const RotateCcw: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const GitCompare: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const History: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const Save: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const KeyRound: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const Ban: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const Link2: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const LogIn: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const QrCode: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const Smartphone: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  // P6 ChatWorkspace icons (verified present in lucide-react@0.468.0 runtime CJS)
  export const ShieldX: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const GitPullRequest: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const FileBarChart: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const CircleDot: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const AlertOctagon: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
  export const OctagonX: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & {
      ref?: React.Ref<SVGSVGElement>;
    }
  >;
}
