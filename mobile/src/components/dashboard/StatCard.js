import React from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

const CONFIG = {
  employees: {
    icon: "people-outline",
    color: "#2563EB",
    bg: "#EFF6FF",
  },
  present: {
    icon: "checkmark-circle-outline",
    color: "#16A34A",
    bg: "#ECFDF5",
  },
  absent: {
    icon: "close-circle-outline",
    color: "#DC2626",
    bg: "#FEF2F2",
  },
  late: {
    icon: "time-outline",
    color: "#D97706",
    bg: "#FEF3C7",
  },
};

export default function StatCard({
  title,
  value,
  type = "employees",
  onPress,
}) {
  const item = CONFIG[type] || CONFIG.employees;

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.wrapper,
        pressed && styles.pressed,
      ]}
      android_ripple={{ color: "#F1F5F9" }}
    >
      <View style={styles.card}>
        <View style={styles.topRow}>
          <View>
            <Text style={styles.title}>{title}</Text>

            <Text style={styles.value}>{value}</Text>
          </View>

          <View
            style={[
              styles.iconBox,
              {
                backgroundColor: item.bg,
              },
            ]}
          >
            <Ionicons
              name={item.icon}
              size={20}
              color={item.color}
            />
          </View>
        </View>

        <View style={styles.bottomRow}>
          <View
            style={[
              styles.statusDot,
              {
                backgroundColor: item.color,
              },
            ]}
          />

          <Text style={styles.liveText}>
            Live Data
          </Text>

          <Ionicons
            name="chevron-forward"
            size={14}
            color="#94A3B8"
            style={styles.arrow}
          />
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    flex: 1,
    marginHorizontal: 5,
    marginVertical: 5,
  },

  pressed: {
    opacity: 0.95,
    transform: [{ scale: 0.98 }],
  },

  card: {
    backgroundColor: "#FFFFFF",

    borderRadius: 18,

    paddingHorizontal: 16,
    paddingVertical: 15,

    height: 118,

    borderWidth: 1,
    borderColor: "#EDF2F7",

    shadowColor: "#0F172A",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: {
      width: 0,
      height: 4,
    },

    elevation: 3,

    justifyContent: "space-between",
  },

  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },

  title: {
    fontSize: 11,
    fontWeight: "600",
    color: "#64748B",
    letterSpacing: 0.4,
    textTransform: "uppercase",
  },

  value: {
    marginTop: 4,
    fontSize: 22,
    fontWeight: "800",
    color: "#0F172A",
  },

  iconBox: {
    width: 40,
    height: 40,
    borderRadius: 12,

    justifyContent: "center",
    alignItems: "center",
  },

  bottomRow: {
    flexDirection: "row",
    alignItems: "center",
  },

  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },

  liveText: {
    marginLeft: 6,
    fontSize: 11,
    color: "#94A3B8",
    fontWeight: "600",
  },

  arrow: {
    marginLeft: "auto",
  },
});