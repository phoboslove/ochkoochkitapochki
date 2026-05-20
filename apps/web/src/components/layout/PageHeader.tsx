export function PageHeader({ title, description, actions, eyebrow }: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  eyebrow?: string;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 mb-6 pb-4 border-b border-border">
      <div>
        {eyebrow && (
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">{eyebrow}</div>
        )}
        <h1 className="text-[22px] font-semibold tracking-tight leading-tight">{title}</h1>
        {description && (
          <p className="mt-1 text-[13px] text-muted-foreground max-w-2xl">{description}</p>
        )}
      </div>
      {actions && <div className="flex gap-2 items-center">{actions}</div>}
    </div>
  );
}
