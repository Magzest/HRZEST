import React from "react";

import {
  View,
  Text,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import PERFORMANCE_THEME from "../../constants/performanceTheme";

export default function PerformanceStatsGrid({

  completedReviews,

  pendingReviews,

  topPerformers,

  averageKPI,

}) {

  const stats = [

    {
      id: 1,

      title: "Completed",

      subtitle: "Reviews",

      value: completedReviews,

      icon: "checkmark-circle",

      color: "#10B981",

      background: "#ECFDF5",

      badge: "Done",

      badgeColor: "#DCFCE7",

      badgeText: "#15803D",
    },

    {
      id: 2,

      title: "Pending",

      subtitle: "Approvals",

      value: pendingReviews,

      icon: "time",

      color: "#F59E0B",

      background: "#FEF3C7",

      badge: "Review",

      badgeColor: "#FEF3C7",

      badgeText: "#B45309",
    },

    {
      id: 3,

      title: "Top Talent",

      subtitle: "Employees",

      value: topPerformers,

      icon: "trophy",

      color: "#7C3AED",

      background: "#F3E8FF",

      badge: "Elite",

      badgeColor: "#F3E8FF",

      badgeText: "#6D28D9",
    },

    {
      id: 4,

      title: "Avg KPI",

      subtitle: "Score",

      value: `${averageKPI}%`,

      icon: "analytics",

      color: "#2563EB",

      background: "#DBEAFE",

      badge: "Monthly",

      badgeColor: "#DBEAFE",

      badgeText: "#1D4ED8",
    },

  ];

  return (

    <View style={styles.container}>

      {stats.map((item) => (

        <View
          key={item.id}
          style={styles.card}
        >

          {/* Accent */}

          <View
            style={[
              styles.accent,
              {
                backgroundColor:
                  item.color,
              },
            ]}
          />

          {/* Header */}

          <View style={styles.header}>

            <View
              style={[
                styles.iconContainer,
                {
                  backgroundColor:
                    item.background,
                },
              ]}
            >

              <Ionicons
                name={item.icon}
                size={22}
                color={item.color}
              />

            </View>

            <View
              style={[
                styles.badge,
                {
                  backgroundColor:
                    item.badgeColor,
                },
              ]}
            >

              <Text
                style={[
                  styles.badgeText,
                  {
                    color:
                      item.badgeText,
                  },
                ]}
              >
                {item.badge}
              </Text>

            </View>

          </View>
                    {/* KPI Value */}

          <Text style={styles.value}>
            {item.value}
          </Text>

          {/* Title */}

          <Text style={styles.title}>
            {item.title}
          </Text>

          {/* Subtitle */}

          <Text style={styles.subtitle}>
            {item.subtitle}
          </Text>

          {/* Divider */}

          <View style={styles.divider} />

          {/* Footer */}

          <View style={styles.footer}>

            <View style={styles.footerLeft}>

              <Ionicons
                name="pulse-outline"
                size={15}
                color={item.color}
              />

              <Text style={styles.footerText}>
                Live Analytics
              </Text>

            </View>

            <View
              style={[
                styles.statusIndicator,
                {
                  backgroundColor: item.color,
                },
              ]}
            />

          </View>

        </View>

      ))}

    </View>

  );

}
const styles = StyleSheet.create({

  container: {
    flexDirection: "row",

    flexWrap: "wrap",

    justifyContent: "space-between",

    marginBottom: 24,
  },

  card: {
    width: "48.8%",

    backgroundColor: "#FFFFFF",

    borderRadius: 24,

    paddingHorizontal: 18,

    paddingTop: 18,

    paddingBottom: 16,

    marginBottom: 16,

    overflow: "hidden",

    borderWidth: 1,

    borderColor: "#EEF2F7",

    shadowColor: "#0F172A",

    shadowOpacity: 0.06,

    shadowRadius: 18,

    shadowOffset: {
      width: 0,
      height: 8,
    },

    elevation: 6,
  },

  accent: {
    position: "absolute",

    top: 0,

    left: 0,

    right: 0,

    height: 5,

    borderTopLeftRadius: 24,

    borderTopRightRadius: 24,
  },

  header: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    marginTop: 4,

    marginBottom: 18,
  },

  iconContainer: {
    width: 56,

    height: 56,

    borderRadius: 18,

    justifyContent: "center",

    alignItems: "center",
  },

  badge: {
    paddingHorizontal: 10,

    paddingVertical: 5,

    borderRadius: 20,

    justifyContent: "center",

    alignItems: "center",
  },

  badgeText: {
    fontSize: 11,

    fontWeight: "800",

    letterSpacing: 0.3,
  },

  value: {
    fontSize: 26,

    fontWeight: "900",

    color: PERFORMANCE_THEME.colors.textPrimary,

    letterSpacing: -0.5,
  },

  title: {
    marginTop: 8,

    fontSize: 16,

    fontWeight: "800",

    color: PERFORMANCE_THEME.colors.textPrimary,
  },

  subtitle: {
    marginTop: 4,

    fontSize: 13,

    fontWeight: "600",

    color: PERFORMANCE_THEME.colors.textMuted,
  },
    divider: {
    height: 1,

    backgroundColor: "#EEF2F7",

    marginTop: 18,

    marginBottom: 14,
  },

  footer: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",
  },

  footerLeft: {
    flexDirection: "row",

    alignItems: "center",

    flex: 1,
  },

  footerText: {
    marginLeft: 6,

    fontSize: 12,

    fontWeight: "700",

    color: "#64748B",
  },

  statusIndicator: {
    width: 10,

    height: 10,

    borderRadius: 5,
  },

});