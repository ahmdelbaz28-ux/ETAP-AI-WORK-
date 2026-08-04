// Augment lucide-react module to include icons that exist at runtime in
// v0.468 but TypeScript under verbatimModuleSyntax cannot verify them from
// the barrel export. Add new icons here as needed.
declare module "lucide-react" {
  export const Cog: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & { ref?: React.Ref<SVGSVGElement> }
  >;
  export const Flame: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & { ref?: React.Ref<SVGSVGElement> }
  >;
  export const CalendarClock: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & { ref?: React.Ref<SVGSVGElement> }
  >;
  export const PlayCircle: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & { ref?: React.Ref<SVGSVGElement> }
  >;
}
