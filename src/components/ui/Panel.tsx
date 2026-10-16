import type { ReactNode } from 'react'

export function Panel({ title, subtitle, action, children, className = '' }: {
  title: string
  subtitle?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel__header">
        <div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
        {action && <div>{action}</div>}
      </div>
      {children}
    </section>
  )
}