import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatSpeed(mbps: number): { value: string; unit: string } {
  if (mbps >= 1000) {
    return { value: (mbps / 1000).toFixed(2), unit: "Gbps" };
  }
  if (mbps >= 1) {
    return { value: mbps.toFixed(1), unit: "Mbps" };
  }
  return { value: (mbps * 1000).toFixed(0), unit: "Kbps" };
}

export function adapterIcon(type: string): string {
  switch (type) {
    case "wifi":       return "wifi";
    case "ethernet":   return "network";
    case "usb_tether": return "smartphone";
    default:           return "globe";
  }
}

export function formatBytes(bytes: number): string {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(2)} GB`;
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(1)} MB`;
  if (bytes >= 1e3) return `${(bytes / 1e3).toFixed(0)} KB`;
  return `${bytes} B`;
}
