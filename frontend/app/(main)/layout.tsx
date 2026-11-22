import Guard from "@/components/Guard";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return <Guard>{children}</Guard>;
}
