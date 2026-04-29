/**
 * One row in a cabinet list: name + role, click opens detail modal.
 *
 * Rendered as a button (not a link) because the action is "open modal,"
 * not "navigate." Keyboard-accessible by default.
 */

import type { LeadershipMember } from "@/lib/types";

type CabinetMemberRowProps = {
  member: LeadershipMember;
  onClick: (member: LeadershipMember) => void;
};

export function CabinetMemberRow({ member, onClick }: CabinetMemberRowProps) {
  return (
    <button
      type="button"
      onClick={() => onClick(member)}
      className="w-full text-left py-2 px-3 rounded hover:bg-gray-100 focus:bg-gray-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-900"
    >
      <span className="font-medium">{member.name}</span>
      <span className="block text-sm text-gray-600">{member.role}</span>
    </button>
  );
}
