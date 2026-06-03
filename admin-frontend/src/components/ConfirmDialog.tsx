export default function ConfirmDialog({ message, onConfirm }: { message: string; onConfirm: () => void }) {
  return <button className="bg-red-600 text-white" onClick={() => { if (confirm(message)) onConfirm(); }}>Подтвердить</button>;
}
