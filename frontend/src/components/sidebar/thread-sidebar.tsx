import { motion } from 'framer-motion';
import { MessageSquare, Plus, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/cn';
import type { ThreadSummary } from '@/lib/thread-state';

export interface ThreadSidebarProps {
  threads: ThreadSummary[];
  activeThreadId: string;
  collapsed: boolean;
  onSelect: (id: string) => void;
  onNewThread: () => void;
  onToggleCollapse: () => void;
}

/**
 * ThreadSidebar — colapsable 240 ↔ 56 px. Lista de hilos mock (5 hardcoded).
 *
 * Spec UX v2: solo se muestra con width >= 1280px (controlado por el padre).
 * Animación de ancho via framer-motion.
 */
export function ThreadSidebar({
  threads,
  activeThreadId,
  collapsed,
  onSelect,
  onNewThread,
  onToggleCollapse,
}: ThreadSidebarProps) {
  return (
    <TooltipProvider delayDuration={200}>
      <motion.aside
        initial={false}
        animate={{ width: collapsed ? 56 : 240 }}
        transition={{ duration: 0.22, ease: 'easeOut' }}
        className="flex h-full shrink-0 flex-col border-r bg-card"
        aria-label="Hilos"
      >
        <div className="flex items-center justify-between gap-1 border-b px-3 py-3">
          {!collapsed && (
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Hilos
            </span>
          )}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={onToggleCollapse}
                aria-label={collapsed ? 'Expandir sidebar' : 'Colapsar sidebar'}
              >
                {collapsed ? (
                  <PanelLeftOpen className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <PanelLeftClose className="h-4 w-4" aria-hidden="true" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              {collapsed ? 'Expandir' : 'Colapsar'}
            </TooltipContent>
          </Tooltip>
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
