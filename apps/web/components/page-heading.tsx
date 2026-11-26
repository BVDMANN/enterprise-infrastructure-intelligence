export function PageHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="mb-7">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">
        {eyebrow}
      </p>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950 md:text-3xl">
            {title}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            {description}
          </p>
        </div>
      </div>
    </div>
  );
}
