import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import AdminDashboard      from '../screens/admin/AdminDashboard';
import EmployeesScreen     from '../screens/admin/EmployeesScreen';
import LeaveRequestsScreen from '../screens/admin/LeaveRequestsScreen';
import ResignationsScreen  from '../screens/admin/ResignationsScreen';
import AdminTicketsScreen  from '../screens/admin/AdminTicketsScreen';
import NotificationsScreen from '../screens/NotificationsScreen';
import { COLORS } from '../config';

const Tab = createBottomTabNavigator();

export default function AdminNavigator() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarStyle: {
          backgroundColor: '#0f2027',
          borderTopColor: 'rgba(255,255,255,0.10)',
          height: 62,
          paddingBottom: 8,
        },
        tabBarActiveTintColor:   '#fff',
        tabBarInactiveTintColor: 'rgba(255,255,255,0.45)',
        tabBarIcon: ({ focused, color, size }) => {
          const icons = {
            Dashboard:     focused ? 'home'              : 'home-outline',
            Employees:     focused ? 'people'            : 'people-outline',
            Leaves:        focused ? 'document-text'     : 'document-text-outline',
            Resignations:  focused ? 'exit'              : 'exit-outline',
            Tickets:       focused ? 'ticket'            : 'ticket-outline',
            Notifications: focused ? 'notifications'     : 'notifications-outline',
          };
          return <Ionicons name={icons[route.name]} size={size} color={color} />;
        },
      })}
    >
      <Tab.Screen name="Dashboard"     component={AdminDashboard}      options={{ tabBarLabel: '🏠 Home' }} />
      <Tab.Screen name="Employees"     component={EmployeesScreen}     options={{ tabBarLabel: '👥 Staff' }} />
      <Tab.Screen name="Leaves"        component={LeaveRequestsScreen} options={{ tabBarLabel: '📋 Leaves' }} />
      <Tab.Screen name="Resignations"  component={ResignationsScreen}  options={{ tabBarLabel: '📤 Resign' }} />
      <Tab.Screen name="Tickets"       component={AdminTicketsScreen}  options={{ tabBarLabel: '🎫 Tickets' }} />
      <Tab.Screen name="Notifications" component={NotificationsScreen} options={{ tabBarLabel: '🔔 Alerts' }} />
    </Tab.Navigator>
  );
}
