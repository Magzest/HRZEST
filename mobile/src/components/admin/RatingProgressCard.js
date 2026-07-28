import React from "react";

import {
  View,
  Text,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import PERFORMANCE_THEME from "../../constants/performanceTheme";

export default function RatingProgressCard({

  averageRating,

  totalReviews,

  fiveStar,

  fourStar,

  threeStar,

  twoStar,

  oneStar,

}) {

  const ratings = [

    {
      star: 5,
      count: fiveStar,
      color: "#10B981",
    },

    {
      star: 4,
      count: fourStar,
      color: "#3B82F6",
    },

    {
      star: 3,
      count: threeStar,
      color: "#F59E0B",
    },

    {
      star: 2,
      count: twoStar,
      color: "#FB923C",
    },

    {
      star: 1,
      count: oneStar,
      color: "#EF4444",
    },

  ];

  const max =
    Math.max(...ratings.map(r => r.count), 1);

  return (

    <View style={styles.card}>

      {/* Accent */}

      <View style={styles.accent} />

      {/* Header */}

      <View style={styles.header}>

        <View>

          <Text style={styles.title}>
            Rating Distribution
          </Text>

          <Text style={styles.subtitle}>
            Employee Performance
          </Text>

        </View>

        <View style={styles.iconContainer}>

          <Ionicons
            name="star"
            size={24}
            color="#F59E0B"
          />

        </View>

      </View>

      {/* Hero */}

      <View style={styles.hero}>

        <Text style={styles.heroValue}>
          {Number(
            averageRating || 0
          ).toFixed(1)}
        </Text>

        <Text style={styles.heroLabel}>
          Average Rating
        </Text>

        <View style={styles.reviewChip}>

          <Ionicons
            name="people-outline"
            size={14}
            color="#2563EB"
          />

          <Text style={styles.reviewText}>
            {totalReviews} Reviews
          </Text>

        </View>

      </View>

      {/* Rating Bars */}

      <View style={styles.ratingContainer}>

        {ratings.map((item) => {

          const width =
            (item.count / max) * 100;

          return (

            <View
              key={item.star}
              style={styles.ratingRow}
            >

              <Text style={styles.starLabel}>
                {item.star}
                ★
              </Text>

              <View style={styles.track}>

                <View
                  style={[
                    styles.fill,
                    {
                      width: `${width}%`,
                      backgroundColor:
                        item.color,
                    },
                  ]}
                />

              </View>

              <Text style={styles.count}>
                {item.count}
              </Text>

            </View>

          );

        })}
                  {/* End Rating Row */}

          );

        })}

      </View>

      {/* ================= Analytics Footer ================= */}

      <View style={styles.divider} />

      <View style={styles.footer}>

        <View style={styles.metricCard}>

          <View
            style={[
              styles.metricIcon,
              {
                backgroundColor: "#ECFDF5",
              },
            ]}
          >

            <Ionicons
              name="trending-up"
              size={18}
              color="#10B981"
            />

          </View>

          <View>

            <Text style={styles.metricValue}>
              +8%
            </Text>

            <Text style={styles.metricLabel}>
              Growth
            </Text>

          </View>

        </View>

        <View style={styles.metricCard}>

          <View
            style={[
              styles.metricIcon,
              {
                backgroundColor: "#DBEAFE",
              },
            ]}
          >

            <Ionicons
              name="analytics"
              size={18}
              color="#2563EB"
            />

          </View>

          <View>

            <Text style={styles.metricValue}>
              92%
            </Text>

            <Text style={styles.metricLabel}>
              Accuracy
            </Text>

          </View>

        </View>

      </View>

    </View>

  );

}
const styles = StyleSheet.create({

  card: {
    backgroundColor: "#FFFFFF",

    borderRadius: 28,

    paddingHorizontal: 22,

    paddingTop: 22,

    paddingBottom: 20,

    marginBottom: 24,

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

    backgroundColor:
      PERFORMANCE_THEME.colors.primary,
  },

  header: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",
  },

  title: {
    fontSize: 18,

    fontWeight: "900",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  subtitle: {
    marginTop: 4,

    fontSize: 13,

    fontWeight: "600",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  iconContainer: {
    width: 56,

    height: 56,

    borderRadius: 18,

    backgroundColor: "#FEF3C7",

    justifyContent: "center",

    alignItems: "center",
  },

  hero: {
    alignItems: "center",

    marginTop: 24,

    marginBottom: 28,
  },

  heroValue: {
    fontSize: 52,

    fontWeight: "900",

    color:
      PERFORMANCE_THEME.colors.textPrimary,

    letterSpacing: -1,
  },

  heroLabel: {
    marginTop: 4,

    fontSize: 14,

    fontWeight: "700",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  reviewChip: {
    marginTop: 14,

    flexDirection: "row",

    alignItems: "center",

    backgroundColor: "#EEF4FF",

    paddingHorizontal: 12,

    paddingVertical: 7,

    borderRadius: 20,
  },

  reviewText: {
    marginLeft: 6,

    fontSize: 12,

    fontWeight: "700",

    color:
      PERFORMANCE_THEME.colors.primary,
  },

  ratingContainer: {
    marginTop: 4,
  },

  ratingRow: {
    flexDirection: "row",

    alignItems: "center",

    marginBottom: 14,
  },

  starLabel: {
    width: 34,

    fontSize: 13,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  track: {
    flex: 1,

    height: 10,

    marginHorizontal: 12,

    backgroundColor: "#E5E7EB",

    borderRadius: 20,

    overflow: "hidden",
  },

  fill: {
    height: "100%",

    borderRadius: 20,
  },

  count: {
    width: 28,

    textAlign: "right",

    fontSize: 13,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.textSecondary,
  },
    divider: {
    height: 1,

    backgroundColor: "#EEF2F7",

    marginTop: 10,

    marginBottom: 18,
  },

  footer: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",
  },

  metricCard: {
    flex: 1,

    flexDirection: "row",

    alignItems: "center",

    backgroundColor: "#F8FAFC",

    borderRadius: 18,

    paddingHorizontal: 14,

    paddingVertical: 14,

    borderWidth: 1,

    borderColor: "#EEF2F7",

    marginHorizontal: 4,
  },

  metricIcon: {
    width: 44,

    height: 44,

    borderRadius: 14,

    justifyContent: "center",

    alignItems: "center",

    marginRight: 12,
  },

  metricValue: {
    fontSize: 18,

    fontWeight: "900",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  metricLabel: {
    marginTop: 2,

    fontSize: 12,

    fontWeight: "700",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

});