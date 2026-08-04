import React from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

const STATUS = {
  Approved: {
    color: "#16A34A",
    bg: "#ECFDF5",
    icon: "checkmark-circle",
  },
  Pending: {
    color: "#D97706",
    bg: "#FFF7ED",
    icon: "time",
  },
  Rejected: {
    color: "#DC2626",
    bg: "#FEF2F2",
    icon: "close-circle",
  },
};

export default function CompOffApplicationCard({
  applications = [],
}) {
  const renderItem = ({ item }) => {
    const status =
      STATUS[item.status] || {
        color: "#64748B",
        bg: "#F1F5F9",
        icon: "ellipse",
      };

    return (
      <View style={styles.card}>
        {/* Header */}

        <View style={styles.header}>
          <View style={styles.dateContainer}>
            <Ionicons
              name="calendar-outline"
              size={18}
              color="#173B8C"
            />

            <Text style={styles.date}>
              {item.date}
            </Text>
          </View>

          <View
            style={[
              styles.badge,
              {
                backgroundColor: status.bg,
              },
            ]}
          >
            <Ionicons
              name={status.icon}
              size={14}
              color={status.color}
            />

            <Text
              style={[
                styles.badgeText,
                {
                  color: status.color,
                },
              ]}
            >
              {item.status}
            </Text>
          </View>
        </View>

        {/* Reason */}

        <View style={styles.section}>
          <Text style={styles.label}>
            Reason
          </Text>

          <Text style={styles.value}>
            {item.reason}
          </Text>
        </View>

        {/* Duration */}

        <View style={styles.footer}>
          <View style={styles.footerItem}>
            <Text style={styles.footerLabel}>
              Days
            </Text>

            <Text style={styles.footerValue}>
              {item.days}
            </Text>
          </View>

          <View style={styles.footerDivider} />

          <View style={styles.footerItem}>
            <Text style={styles.footerLabel}>
              Approved By
            </Text>

            <Text style={styles.footerValue}>
              {item.approvedBy}
            </Text>
          </View>
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>
        Comp-off Applications
      </Text>

      <Text style={styles.subtitle}>
        Your submitted requests
      </Text>

      <FlatList
        data={applications}
        scrollEnabled={false}
        keyExtractor={(item, index) =>
          index.toString()
        }
        renderItem={renderItem}
        ItemSeparatorComponent={() => (
          <View style={{ height: 16 }} />
        )}
        ListEmptyComponent={() => (
          <View style={{ backgroundColor: "#FFFFFF", borderRadius: 18, padding: 22, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: "#E2E8F0" }}>
            <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: "#F1F5F9", justifyContent: "center", alignItems: "center", marginBottom: 8 }}>
              <Ionicons name="document-text-outline" size={24} color="#173B8C" />
            </View>
            <Text style={{ fontSize: 15, fontWeight: "700", color: "#0F172A" }}>
              No Comp-Off Applications Submitted
            </Text>
            <Text style={{ fontSize: 13, fontWeight: "500", color: "#64748B", marginTop: 4, textAlign: "center" }}>
              Your comp-off leave requests will appear here once applied.
            </Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: 24,
  },

  title: {
    fontSize: 16,
    fontWeight: "800",
    color: "#0F172A",
  },

  subtitle: {
    marginTop: 2,
    marginBottom: 12,
    color: "#64748B",
    fontSize: 13,
    fontWeight: "600",
  },

  card: {
    backgroundColor: "#FFFFFF",

    borderRadius: 22,

    padding: 20,

    borderWidth: 1,
    borderColor: "#E8EDF5",

    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 14,
    shadowOffset: {
      width: 0,
      height: 6,
    },

    elevation: 4,
  },

  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },

  dateContainer: {
    flexDirection: "row",
    alignItems: "center",
  },

  date: {
    marginLeft: 8,
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
  },

  badge: {
    flexDirection: "row",
    alignItems: "center",

    paddingHorizontal: 12,
    paddingVertical: 7,

    borderRadius: 20,
  },

  badgeText: {
    marginLeft: 5,
    fontWeight: "700",
    fontSize: 12,
  },

  section: {
    marginTop: 18,
  },

  label: {
    fontSize: 12,
    color: "#94A3B8",
    fontWeight: "600",
    marginBottom: 6,
  },

  value: {
    fontSize: 15,
    color: "#334155",
    lineHeight: 22,
    fontWeight: "500",
  },

  footer: {
    flexDirection: "row",

    marginTop: 22,

    borderTopWidth: 1,
    borderTopColor: "#EEF2F7",

    paddingTop: 16,
  },

  footerItem: {
    flex: 1,
    alignItems: "center",
  },

  footerDivider: {
    width: 1,
    backgroundColor: "#EEF2F7",
  },

  footerLabel: {
    fontSize: 12,
    color: "#94A3B8",
    fontWeight: "600",
  },

  footerValue: {
    marginTop: 6,
    fontSize: 15,
    color: "#0F172A",
    fontWeight: "700",
  },
});