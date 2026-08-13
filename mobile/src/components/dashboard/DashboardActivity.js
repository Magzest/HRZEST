import React from 'react';
import {
  View,
  Text,
  StyleSheet,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function DashboardActivity() {

  const activities = [
    {
      id: 1,
      icon: 'person-add',
      color: '#2563EB',
      bg: '#E8F1FF',
      title: 'New employee joined',
      subtitle: 'Employee records updated',
      time: 'Today',
    },
    {
      id: 2,
      icon: 'checkmark-circle',
      color: '#16A34A',
      bg: '#ECFDF5',
      title: 'Attendance synchronized',
      subtitle: "Today's attendance has been updated",
      time: '5 min ago',
    },
    {
      id: 3,
      icon: 'document-text',
      color: '#EA580C',
      bg: '#FFF7ED',
      title: 'Leave requests pending',
      subtitle: 'Administrator action required',
      time: '12 min ago',
    },
  ];

  return (
    <View style={styles.container}>

      <View style={styles.header}>

        <Text style={styles.heading}>
          Recent Activity
        </Text>

        <Ionicons
          name="time-outline"
          size={20}
          color="#64748B"
        />

      </View>

      {activities.map((item, index) => (

        <View
          key={item.id}
          style={[
            styles.row,
            index === activities.length - 1 && {
              borderBottomWidth: 0,
            },
          ]}
        >

          <View
            style={[
              styles.iconContainer,
              {
                backgroundColor: item.bg,
              },
            ]}
          >

            <Ionicons
              name={item.icon}
              size={22}
              color={item.color}
            />

          </View>

          <View style={styles.content}>

            <Text style={styles.title}>
              {item.title}
            </Text>

            <Text style={styles.subtitle}>
              {item.subtitle}
            </Text>

          </View>

          <Text style={styles.time}>
            {item.time}
          </Text>

        </View>

      ))}

    </View>
  );

}

const styles = StyleSheet.create({

  container: {

    backgroundColor: '#FFFFFF',

    borderRadius: 22,

    marginTop: 24,

    padding: 20,

    shadowColor: '#000',

    shadowOpacity: 0.05,

    shadowRadius: 15,

    shadowOffset: {
      width: 0,
      height: 6,
    },

    elevation: 5,

    borderWidth: 1,

    borderColor: '#EEF2F7',

  },

  header: {

    flexDirection: 'row',

    justifyContent: 'space-between',

    alignItems: 'center',

    marginBottom: 18,

  },

  heading: {

    fontSize: 14,

    fontWeight: '700',

    color: '#111827',

  },

  row: {

    flexDirection: 'row',

    alignItems: 'center',

    paddingVertical: 14,

    borderBottomWidth: 1,

    borderBottomColor: '#EEF2F7',

  },

  iconContainer: {

    width: 48,

    height: 48,

    borderRadius: 14,

    justifyContent: 'center',

    alignItems: 'center',

    marginRight: 14,

  },

  content: {

    flex: 1,

  },

  title: {

    fontSize: 13,

    fontWeight: '700',

    color: '#111827',

  },

  subtitle: {

    marginTop: 4,

    fontSize: 12,

    color: '#64748B',

  },

  time: {

    fontSize: 11,

    color: '#94A3B8',

    fontWeight: '600',

  },

});