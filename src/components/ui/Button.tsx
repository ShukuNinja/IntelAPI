import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
}
export function Button({ children, variant = 'secondary', size = 'md', className = '', ...props }: Props) {
  return <button className={`button button--${variant} button--${size} ${className}`} {...props}>{children}</button>
}