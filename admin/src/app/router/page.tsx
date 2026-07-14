import { RoutingConsole } from "@/components/RoutingConsole";
import { getRoutingAdminSnapshot } from "@/lib/data";

export const dynamic = "force-dynamic";

export default function RouterPage() {
  return <RoutingConsole initial={getRoutingAdminSnapshot()} />;
}
