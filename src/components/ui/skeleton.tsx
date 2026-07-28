import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("shimmer-bg rounded-md", className)} {...props} />;
}

export { Skeleton };
