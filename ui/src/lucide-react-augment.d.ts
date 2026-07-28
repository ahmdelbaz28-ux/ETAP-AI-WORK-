// Augment lucide-react module to include icons that TypeScript under
// verbatimModuleSyntax cannot verify from the barrel export.
// These icons exist at runtime in v0.468 but tsc fails to resolve them
// from the single-line `export { ... }` statement in lucide-react.d.ts.
// Adding them here as explicit `declare module` augmentations lets tsc
// see them without disabling verbatimModuleSyntax.
// Icons added:
//   - Cog, Flame (pre-existing — needed by Settings page)
//   - Pencil (added by P1 DualControl PR — needed by AssetManagement edit button)
//   - QrCode (added by P1 DualControl PR — needed by DualControl QR secret modal)
declare module "lucide-react" {
  export const Cog: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & { ref?: React.Ref<SVGSVGElement> }
  >;
  export const Flame: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & { ref?: React.Ref<SVGSVGElement> }
  >;
  export const Pencil: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & { ref?: React.Ref<SVGSVGElement> }
  >;
  export const QrCode: React.ForwardRefExoticComponent<
    Omit<React.SVGProps<SVGSVGElement>, "ref"> & { ref?: React.Ref<SVGSVGElement> }
  >;
}
