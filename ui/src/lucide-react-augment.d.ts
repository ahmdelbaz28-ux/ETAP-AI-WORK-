// Augment lucide-react module to include Cog and Flame icons
// These icons exist at runtime in v0.468 but TypeScript under
// verbatimModuleSyntax cannot verify them from the barrel export.
declare module "lucide-react" {
  export const Cog: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & { ref?: React.Ref<SVGSVGElement> }
  >;
  export const Flame: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & { ref?: React.Ref<SVGSVGElement> }
  >;
}
