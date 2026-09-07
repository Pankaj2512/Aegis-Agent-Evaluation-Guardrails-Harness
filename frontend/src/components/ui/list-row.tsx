import Link from "next/link";
import { cn } from "@/lib/utils";

interface ListRowProps {
  href?: string;
  onClick?: () => void;
  children: React.ReactNode;
  className?: string;
}

export function ListRow({ href, onClick, children, className }: ListRowProps) {
  const rowClass = cn(
    "group flex min-h-[72px] items-center gap-4 px-5 py-3 text-sm transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/30",
    className
  );

  if (href) {
    return (
      <Link href={href} className={rowClass}>
        {children}
      </Link>
    );
  }

  return (
    <button type="button" onClick={onClick} className={cn(rowClass, "w-full text-left")}>
      {children}
    </button>
  );
}
