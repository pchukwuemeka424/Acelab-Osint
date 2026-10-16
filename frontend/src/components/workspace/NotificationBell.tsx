import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Bell } from "lucide-react"
import { useState } from "react"
import { api } from "../../api/client"

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const notes = useQuery({ queryKey: ["notifications"], queryFn: api.notifications })
  const markRead = useMutation({
    mutationFn: api.readNotifications,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  })

  return (
    <div className="relative">
      <button
        type="button"
        aria-label="Notifications"
        aria-expanded={open}
        className="relative flex h-8 w-8 items-center justify-center rounded-full text-slate-500 hover:bg-white hover:text-slate-900"
        onClick={() => {
          setOpen((value) => !value)
          if (notes.data?.unread) markRead.mutate()
        }}
      >
        <Bell size={16} />
        {notes.data?.unread && <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-rose-500 ring-2 ring-slate-50" />}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-72 overflow-hidden rounded-xl border border-slate-200 bg-white p-2 text-[11px] text-slate-800 shadow-[0_16px_40px_-24px_rgba(15,23,42,0.45)]">
          {(notes.data?.items || []).length === 0 && <p className="px-2 py-1.5 text-slate-500">No notifications.</p>}
          {(notes.data?.items || []).map((item) => (
            <div key={item.id} className="border-b border-slate-100 px-2 py-1.5 last:border-0">
              <div className="font-medium text-slate-900">{item.action.replaceAll("_", " ")}</div>
              <div className="truncate text-slate-500">{item.target}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
