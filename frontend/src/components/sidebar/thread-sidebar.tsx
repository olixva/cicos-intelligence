import { motion } from 'framer-motion';
import { MessageSquare, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/cn';
import type { ThreadSummary } from '@/lib/thread-state';

export interface ThreadSidebarProps {
  threads: ThreadSummary[];
  activeThreadId: string;
  /** Se conserva por compatibilidad de tipos; hoy siempre es false. */
  collapsed?: boolean;
  onSelect: (id: string) => void;
  onNewThread: () => void;
}

/**
 * ThreadSidebar — lista los hilos reales persistidos por `thread-store`.
 *
 * Ancho fijo de 240 px y altura completa. La variante contraída se retiró:
 * a 56 px sólo quedaban iconos de chat idénticos, sin manera de saber qué
 * conversación era cada uno.
 *
 * Spec UX v2: sólo se muestra con width >= 1280px (lo controla el padre).
 */
export function ThreadSidebar({
  threads,
  activeThreadId,
  onSelect,
  onNewThread,
}: ThreadSidebarProps) {
  const collapsed = false;
  return (
    <TooltipProvider delayDuration={200}>
      <motion.aside
        initial={false}
        animate={{ width: collapsed ? 56 : 240 }}
        transition={{ duration: 0.22, ease: 'easeOut' }}
        className="flex shrink-0 flex-col self-stretch border-r bg-card"
        aria-label="Hilos"
      >
        <div className="flex items-center gap-1 border-b px-3 py-3">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Hilos
          </span>
        </div>

        <div className="px-2 py-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                onClick={onNewThread}
                className={cn('w-full', collapsed && 'h-9 w-9 p-0')}
                aria-label="Nuevo hilo"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                {!collapsed && <span className="text-xs">Nuevo hilo</span>}
              </Button>
            </TooltipTrigger>
            {collapsed && <TooltipContent side="right">Nuevo hilo</TooltipContent>}
          </Tooltip>
        </div>

        <ul className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 pb-2">
          {threads.map((t) => {
            const isActive = t.id === activeThreadId;
            const ButtonEl = (
              <button
                type="button"
                key={t.id}
                onClick={() => onSelect(t.id)}
                aria-current={isActive ? 'true' : undefined}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-xs',
                  'transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  isActive && 'bg-primary/10 text-primary',
                  collapsed && 'justify-center',
                )}
              >
                <MessageSquare className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                {!collapsed && (
                  <span className="line-clamp-2 flex-1 text-pretty">{t.title}</span>
                )}
              </button>
            );
            return (
              <li key={t.id}>
                {collapsed ? (
                  <Tooltip>
                    <TooltipTrigger asChild>{ButtonEl}</TooltipTrigger>
                    <TooltipContent side="right">{t.title}</TooltipContent>
                  </Tooltip>
                ) : (
                  ButtonEl
                )}
              </li>
            );
          })}
        </ul>
      </motion.aside>
    </TooltipProvider>
  );
}
