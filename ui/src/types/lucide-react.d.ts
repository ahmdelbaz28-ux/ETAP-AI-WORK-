declare module 'lucide-react' {
  import { SVGProps, RefAttributes } from 'react';

  type IconProps = React.FC<SVGProps<SVGSVGElement>>;

  const createLucideIcon: (name: string, ...icons: any[]) => IconProps;

  export const createElement: (
    type: string,
    props?: SVGProps<SVGSVGElement> & RefAttributes<SVGSVGElement>
  ) => React.ReactElement | null;

  export * from '../node_modules/lucide-react/dist/esm/lucide-react.mjs';
}