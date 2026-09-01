import { User } from 'lucide-react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { cn } from '@/lib/cn';
import type { MessageUser } from '@/lib/thread-state';

export interface UserMessageProps {
  message: MessageUser;
}

/**
 * UserMessage — Origin UI comp-456 AI bubble-style (lado user).
 *
 * Burbuja alineada a la derecha, fondo `--color-surface-2`, avatar a la
 * izquierda con icono User de lucide.
 */
export function UserMessage({ message }: UserMessageProps) {
  return (
    <article
      aria-label="Mensaje del usuario"
      className="flex items-start gap-3"
      data-role="user"
    >
      <Avatar className="h-8 w-8 border bg-primary text-primary-foreground">
        <AvatarFallback className="bg-primary text-primary-foreground">
          <User className="h-4 w-4" aria-hidden="true" />
        </AvatarFallback>
      </Avatar>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <header className="flex items-center gap-2 text-[10px] text-muted-foreground">
          <span className="font-medium text-foreground">Tú</span>
          <span aria-hidden="true">·</span>
          <span>modo {message.mode}</span>
        </header>
        <div
          className={cn(
            'rounded-lg border px-3 py-2 text-sm',
            'bg-[color:var(--color-surface-2)] text-foreground',
          )}
        >
          <p className="whitespace-pre-wrap text-pretty">{message.text}</p>
        </div>
      </div>
    </article>
  );
}
