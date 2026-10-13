// Editable shadcn/ui Button pattern (MIT): https://ui.shadcn.com/docs/components/button
import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-45 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  { variants: {
    variant: {
      default: 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm',
      outline: 'border border-border bg-card hover:bg-muted text-foreground',
      ghost: 'hover:bg-muted text-foreground',
    },
    size: { default: 'h-10 px-4 py-2', sm: 'h-9 px-3', icon: 'size-10' },
  }, defaultVariants: { variant: 'default', size: 'default' } },
);

type ButtonProps = React.ComponentProps<'button'> & VariantProps<typeof buttonVariants> & { asChild?: boolean };
export function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const Component = asChild ? Slot : 'button';
  return <Component className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}
